import copy
import logging
import json
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

# Logging is configured centrally in ``config.settings``.  Avoid opening a
# project-local file at import time: web workers, management commands and test
# runners can import this module concurrently, and Windows locks that file.
logger = logging.getLogger(__name__)

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import IntegrityError, transaction
from django.template import loader
from django.utils.text import slugify
from bs4 import BeautifulSoup

from .models import Theme
from .validators import (
    validate_ownbasket_theme,
    validate_static_theme,
    _resolve_preview_path,
    _is_js_framework_theme,
)

IGNORED_THEME_DIRS = {
    "__pycache__",
    "management",
    "migrations",
    "templatetags",
}

MAX_THEME_ZIP_BYTES = 50 * 1024 * 1024
MAX_THEME_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_THEME_MEMBERS = 5000
BLOCKED_EXTENSIONS = {
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".exe",
    ".msi",
    ".ps1",
    ".pyd",
    ".scr",
    ".sh",
}


@dataclass
class ThemeScanResult:
    folder_name: str
    path: Path
    metadata: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    theme: Theme | None = None
    created: bool = False
    updated: bool = False

    @property
    def is_valid(self):
        return not self.errors


@dataclass
class ThemeUploadResult:
    theme: Theme | None = None
    folder_name: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_static_import: bool = False

    @property
    def is_valid(self):
        return not self.errors


def get_theme_packages_root():
    return Path(settings.BASE_DIR) / "themes"


def get_theme_storage_root():
    root = get_theme_packages_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_default_theme_payload():
    return {
        "name": "Default Theme",
        "slug": "default",
        "version": "1.0",
        "author": "OwnBasket",
        "description": "Built-in OwnBasket fallback theme.",
        "theme_folder": "default",
        "header_layout": "header1",
        "hero_layout": "hero1",
        "category_layout": "layout1",
        "brand_layout": "layout1",
        "product_card_layout": "card1",
        "product_detail_layout": "layout1",
        "cart_layout": "layout1",
        "checkout_layout": "layout1",
        "footer_layout": "footer1",
        "brand_primary_color": "#ffb800",
        "brand_secondary_color": "#232f3e",
        "brand_accent_color": "#ffb800",
        "bg_body_color": "#f4f6f9",
        "text_primary_color": "#1a1a1a",
        "border_global_color": "#eaecf0",
        "btn_primary_bg_color": "#ffb800",
        "btn_primary_hover_bg_color": "#e0a200",
        "font_family": "Inter",
        "border_radius": "10px",
        "button_style": "rounded",
        "animation_style": "none",
    }


def ensure_default_theme():
    payload = get_default_theme_payload()
    theme, _ = Theme.objects.get_or_create(
        slug=payload["slug"],
        defaults=payload,
    )
    return theme


def _is_unsafe_zip_name(name):
    normalized = name.replace("\\", "/")
    path = Path(normalized)
    if normalized.startswith("/") or normalized.startswith("../"):
        return True
    if ".." in path.parts:
        return True
    if Path(path.name).suffix.lower() in BLOCKED_EXTENSIONS:
        return True
    return False


def _safe_extract_zip(zip_file, destination):
    destination = Path(destination).resolve()
    members = zip_file.infolist()
    if len(members) > MAX_THEME_MEMBERS:
        raise ValidationError('Theme ZIP contains too many files.')
    if sum(member.file_size for member in members) > MAX_THEME_UNCOMPRESSED_BYTES:
        raise ValidationError('Theme ZIP expands beyond the safe uncompressed size limit.')
    for member in members:
        if _is_unsafe_zip_name(member.filename):
            raise ValidationError(f"Unsafe file in ZIP: {member.filename}")

        target_path = (destination / member.filename).resolve()
        if destination not in target_path.parents and target_path != destination:
            raise ValidationError(f"Unsafe ZIP path: {member.filename}")

    zip_file.extractall(destination)


def _find_theme_root_and_type(extract_dir: Path) -> tuple[Path, str]:
    """
    Find the theme root directory and determine its type.
    Returns a tuple of (path_to_root, theme_type).
    Theme types can be 'ownbasket' or 'static'.
    """
    # First, look for theme.json for a native OwnBasket theme.
    for root, _, files in os.walk(extract_dir):
        if "theme.json" in files:
            return Path(root), "ownbasket"

    # If not found, check for JS frameworks. If found, we can't handle it.
    if _is_js_framework_theme(extract_dir):
        # Check the root first
        if any(f.lower() == "package.json" for f in os.listdir(extract_dir)):
            return extract_dir, "javascript"
    # then check subdirectories
    for root, _, files in os.walk(extract_dir):
        if "package.json" in files:
            if _is_js_framework_theme(Path(root)):
                return Path(root), "javascript"

    # If not a JS framework, assume it's a static HTML theme.
    # The "root" is the directory with the most HTML files.
    best_candidate = extract_dir
    max_html_files = -1
    for root, _, files in os.walk(extract_dir):
        html_count = sum(1 for f in files if f.lower().endswith(".html"))
        if html_count > max_html_files:
            max_html_files = html_count
            best_candidate = Path(root)

    if max_html_files > 0:
        return best_candidate, "static"

    # If no HTML files are found, it's an invalid theme structure.
    raise ValidationError(
        "The uploaded ZIP is not a valid theme. No 'theme.json' or '*.html' files could be found."
    )


def _unique_theme_folder(slug):
    root = get_theme_storage_root()
    base_name = slugify(slug) or "theme"
    candidate = base_name
    counter = 2
    while (root / candidate).exists() or Theme.objects.filter(
        theme_folder=candidate
    ).exists():
        candidate = f"{base_name}-{counter}"
        counter += 1
    return candidate


def _copy_theme_package(source_dir, folder_name):
    destination = get_theme_storage_root() / folder_name
    if destination.exists():
        raise ValidationError(f"Theme folder already exists: {folder_name}")
    shutil.copytree(source_dir, destination)
    return destination


def _rewrite_asset_paths(theme_dir: Path, theme_folder: str, warnings: list[str]):
    """
    Scans HTML files in a theme and rewrites relative asset paths to use
    the Django {% static %} template tag.
    """
    # Look for all HTML files in the theme directory, recursively.
    html_files = list(theme_dir.glob("**/*.html"))
    if not html_files:
        warnings.append("No HTML files found to process for asset path rewriting.")
        return

    # The tag to add to the top of each HTML file.
    load_static_tag = "{% load static %}\n"

    for html_file in html_files:
        try:
            with html_file.open("r+", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                soup = BeautifulSoup(content, "html.parser")

                # Check if {% load static %} is already present
                if "{% load static %}" not in content:
                    content = load_static_tag + content
                    f.seek(0)
                    f.write(content)
                    f.truncate()
                    # Re-read content after modification
                    content = f.read()
                    soup = BeautifulSoup(content, "html.parser")

                has_changes = False
                tags_to_process = soup.find_all(["link", "script", "img", "a"])

                for tag in tags_to_process:
                    attr = ""
                    if tag.name == "link" and tag.has_attr("href"):
                        attr = "href"
                    elif tag.name in ["script", "img"] and tag.has_attr("src"):
                        attr = "src"
                    elif (
                        tag.name == "a"
                        and tag.has_attr("href")
                        and not tag["href"].startswith("#")
                    ):
                        # Also check anchors, but only for file-like links
                        href = tag["href"]
                        if not any(
                            href.startswith(p)
                            for p in ["http", "https", "//", "mailto:", "tel:"]
                        ):
                            attr = "href"

                    if not attr:
                        continue

                    original_path = tag[attr]

                    # Skip empty, absolute, or special-protocol URLs
                    if (
                        not original_path
                        or urlparse(original_path).scheme
                        or original_path.startswith(("/", "#", "{%", "{{"))
                    ):
                        continue

                    # Construct the absolute path on the filesystem to see if the asset exists
                    # The asset path is relative to the HTML file's location
                    asset_file_path = (html_file.parent / original_path).resolve()

                    if asset_file_path.is_file():
                        try:
                            # Find the asset's path relative to the theme's root directory
                            relative_asset_path = asset_file_path.relative_to(theme_dir)

                            # Build the new path for the static tag
                            new_path = f"{{% static 'themes/{theme_folder}/{relative_asset_path.as_posix()}' %}}"

                            # Replace the attribute value
                            tag[attr] = new_path
                            has_changes = True
                            warnings.append(
                                f"Rewrote path in {html_file.name}: '{original_path}' -> '{new_path}'"
                            )
                        except ValueError:
                            # This occurs if the asset is outside the theme directory (e.g., ../../....)
                            warnings.append(
                                f"Asset '{original_path}' in {html_file.name} points outside the theme directory and was not rewritten."
                            )
                    else:
                        warnings.append(
                            f"Asset '{original_path}' in {html_file.name} not found on disk, skipping rewrite."
                        )

                if has_changes:
                    f.seek(0)
                    # We need to write the modified soup back to the file
                    # We also need to add the load static tag at the top of the file
                    # The beautifulsoup output might not be perfectly formatted, but it's functional
                    html_output = soup.prettify()
                    if "{% load static %}" not in html_output:
                        html_output = load_static_tag + html_output

                    f.write(html_output)
                    f.truncate()

        except Exception as e:
            warnings.append(f"Could not process file {html_file.name}: {e}")


def install_theme_zip(uploaded_file):
    if uploaded_file.size > MAX_THEME_ZIP_BYTES:
        return ThemeUploadResult(errors=["Theme ZIP is too large (max 50 MB)."])

    filename = uploaded_file.name or ""
    if not filename.lower().endswith(".zip"):
        return ThemeUploadResult(errors=["Only .zip theme uploads are allowed."])

    temp_root = Path(settings.BASE_DIR) / "media" / "theme_uploads" / "_tmp"
    work_dir = (
        temp_root / f"upload-{slugify(Path(filename).stem)}-{os.urandom(4).hex()}"
    )

    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        zip_path = work_dir / "theme.zip"
        with zip_path.open("wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        if not zipfile.is_zipfile(zip_path):
            return ThemeUploadResult(
                errors=["Uploaded file is not a valid ZIP archive."]
            )

        extract_dir = work_dir / "extract"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as zip_ref:
            _safe_extract_zip(zip_ref, extract_dir)

        source_theme_dir, theme_type = _find_theme_root_and_type(extract_dir)

        if theme_type == "javascript":
            return ThemeUploadResult(
                errors=[
                    "This appears to be a React/Next.js project. "
                    "Please upload a static HTML/Bootstrap theme instead."
                ]
            )

        is_static_import = theme_type == "static"
        metadata, errors, warnings = (
            validate_static_theme(source_theme_dir, filename)
            if is_static_import
            else validate_ownbasket_theme(source_theme_dir)
        )

        if errors:
            return ThemeUploadResult(errors=errors)

        slug = slugify(metadata.get("slug") or metadata.get("name") or "new-theme")
        folder_name = _unique_theme_folder(slug)
        installed_dir = _copy_theme_package(source_theme_dir, folder_name)

        # --- Asset Path Rewriting ---
        if is_static_import:
            try:
                _rewrite_asset_paths(installed_dir, folder_name, warnings)
            except Exception as e:
                warnings.append(f"An error occurred during asset conversion: {e}")

        # Re-run validation on the final installed directory to confirm structure
        final_metadata, final_errors, final_warnings = validate_ownbasket_theme(
            installed_dir
        )

        if final_errors:
            # For static themes, we expect certain "errors" like missing folders, which we can ignore.
            if not is_static_import:
                shutil.rmtree(installed_dir, ignore_errors=True)
                return ThemeUploadResult(errors=final_errors)
            else:
                # For static themes, these are not show-stoppers, but we might want to log them.
                warnings.extend(final_errors)

        defaults = _metadata_to_theme_defaults(final_metadata, folder_name)

        try:
            with transaction.atomic():
                theme = Theme.objects.create(**defaults)
            _sync_preview_image(
                theme, _resolve_preview_path(installed_dir, final_metadata)
            )
        except IntegrityError as exc:
            shutil.rmtree(installed_dir, ignore_errors=True)
            return ThemeUploadResult(
                errors=[f"A theme with this name or slug already exists: {exc}"]
            )

        return ThemeUploadResult(
            theme=theme,
            folder_name=folder_name,
            warnings=warnings + final_warnings,
            is_static_import=is_static_import,
        )

    except ValidationError as exc:
        return ThemeUploadResult(
            errors=exc.messages if hasattr(exc, "messages") else [str(exc)]
        )
    except (zipfile.BadZipFile, OSError) as exc:
        return ThemeUploadResult(errors=[f"Error processing ZIP file: {exc}"])
    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)


def iter_theme_package_dirs():
    themes_root = get_theme_packages_root()
    if not themes_root.exists():
        return []

    theme_dirs = []
    for child in themes_root.iterdir():
        if not child.is_dir() or child.name in IGNORED_THEME_DIRS:
            continue
        if child.name.startswith("."):
            continue
        theme_dirs.append(child)
    return sorted(theme_dirs, key=lambda path: path.name.lower())


def _metadata_to_theme_defaults(metadata, folder_name):
    slug = slugify(metadata.get("slug") or metadata.get("name") or folder_name)
    return {
        "name": metadata.get("name") or folder_name.replace("_", " ").title(),
        "slug": slug,
        "description": metadata.get("description", ""),
        "version": metadata.get("version", "1.0"),
        "author": metadata.get("author", "OwnBasket"),
        "theme_folder": folder_name,
        "is_custom": False,
        "header_layout": metadata.get(
            "header_layout", metadata.get("header", "header1")
        ),
        "hero_layout": metadata.get("hero_layout", metadata.get("hero", "hero1")),
        "category_layout": metadata.get(
            "category_layout", metadata.get("category", "layout1")
        ),
        "brand_layout": metadata.get("brand_layout", metadata.get("brand", "layout1")),
        "product_card_layout": metadata.get(
            "product_card_layout", metadata.get("product_card", "card1")
        ),
        "product_detail_layout": metadata.get(
            "product_detail_layout", metadata.get("product_detail", "layout1")
        ),
        "cart_layout": metadata.get("cart_layout", metadata.get("cart", "layout1")),
        "checkout_layout": metadata.get(
            "checkout_layout", metadata.get("checkout", "layout1")
        ),
        "footer_layout": metadata.get(
            "footer_layout", metadata.get("footer", "footer1")
        ),
        "brand_primary_color": metadata.get("brand_primary_color", metadata.get("primary_color", "#ffb800")),
        "brand_secondary_color": metadata.get("brand_secondary_color", metadata.get("secondary_color", "#232f3e")),
        "brand_accent_color": metadata.get("brand_accent_color", metadata.get("accent_color", "#ffb800")),
        "bg_body_color": metadata.get("bg_body_color", metadata.get("bg_color", "#f4f6f9")),
        "text_primary_color": metadata.get("text_primary_color", metadata.get("text_color", "#1a1a1a")),
        "border_global_color": metadata.get("border_global_color", metadata.get("border_color", "#eaecf0")),
        "btn_primary_bg_color": metadata.get("btn_primary_bg_color", metadata.get("button_color", "#ffb800")),
        "btn_primary_hover_bg_color": metadata.get("btn_primary_hover_bg_color", metadata.get("hover_color", "#e0a200")),
        "font_family": metadata.get("font_family", "Inter"),
        "border_radius": metadata.get("border_radius", "10px"),
        "button_style": metadata.get("button_style", "rounded"),
        "animation_style": metadata.get("animation_style", "none"),
    }


def _sync_preview_image(theme, preview_path):
    if not preview_path:
        return
    current_name = Path(theme.preview_image.name).name if theme.preview_image else ""
    target_name = f"{theme.slug}-{preview_path.name}"
    if current_name == target_name:
        return
    with preview_path.open("rb") as image_file:
        theme.preview_image.save(target_name, File(image_file), save=True)


def scan_theme_packages():
    ensure_default_theme()
    results = []

    for theme_dir in iter_theme_package_dirs():
        metadata, errors, warnings = validate_ownbasket_theme(theme_dir)
        result = ThemeScanResult(
            folder_name=theme_dir.name,
            path=theme_dir,
            metadata=metadata,
            errors=errors,
            warnings=warnings,
        )
        results.append(result)
        if not result.is_valid:
            continue

        defaults = _metadata_to_theme_defaults(result.metadata, result.folder_name)
        preview_path = _resolve_preview_path(theme_dir, result.metadata)
        lookup = {"theme_folder": result.folder_name}

        try:
            with transaction.atomic():
                theme, created = Theme.objects.update_or_create(
                    **lookup,
                    defaults=defaults,
                )
        except IntegrityError as exc:
            result.errors.append(
                f"Could not save theme because of a duplicate name or slug: {exc}."
            )
            continue

        _sync_preview_image(theme, preview_path)
        result.theme = theme
        result.created = created
        result.updated = not created

    return results


def get_theme_validation_map():
    validation_map = {}
    for theme_dir in iter_theme_package_dirs():
        metadata, errors, warnings = validate_ownbasket_theme(theme_dir)
        validation_map[theme_dir.name] = ThemeScanResult(
            folder_name=theme_dir.name,
            path=theme_dir,
            metadata=metadata,
            errors=errors,
            warnings=warnings,
        )
    return validation_map


def get_active_theme(request):
    """
    A centralized service to get the active theme for a request.
    It handles preview themes, cached active themes, and fallbacks.
    This is the single source of truth for the current theme.
    """
    active_theme = None
    preview_theme_id = request.session.get("preview_theme_id")
    preview_data = request.session.get("preview_theme_data")

    # 1. Handle Preview Theme
    if preview_theme_id:
        cache_key = f"preview_theme_{preview_theme_id}"
        active_theme = cache.get(cache_key)
        if not active_theme:
            active_theme = Theme.objects.filter(pk=preview_theme_id).first()
            if active_theme:
                cache.set(cache_key, active_theme)

        # If there's preview data, apply it on top of the theme object
        # This creates a temporary, in-memory version of the theme
        if active_theme and preview_data and isinstance(preview_data, dict):
            # Create a copy to avoid modifying the cached object
            theme_copy = copy.copy(active_theme)
            for key, value in preview_data.items():
                setattr(theme_copy, key, value)
            return theme_copy

    # 2. Handle Active Theme (if not in preview)
    if not active_theme:
        cache_key = "active_theme"
        active_theme = cache.get(cache_key)
        if not active_theme:
            active_theme = Theme.objects.filter(is_active=True).first()
            cache.set(cache_key, active_theme)

    # 3. Final fallback to default theme if no active/preview theme is found
    if not active_theme:
        cache_key = "default_theme"
        active_theme = cache.get(cache_key)
        if not active_theme:
            active_theme = ensure_default_theme()
            cache.set(cache_key, active_theme)

    return active_theme


LAYOUT_REGISTRY = {
    # component_name: (theme_model_attribute_name, template_subfolder_name)
    "header": ("header_layout", "header"),
    "footer": ("footer_layout", "footer"),
    "hero": ("hero_layout", "hero"),
    "brand": ("brand_layout", "brands"),
    "category": ("category_layout", "categories"),
    "product_list": ("product_card_layout", "product_card"),
    "product_detail": ("product_detail_layout", "product_detail"),
    "cart": ("cart_layout", "cart"),
    "checkout": ("checkout_layout", "checkout"),
}


class LayoutResolver:
    """
    A centralized, cached resolver for theme layout templates.
    It uses a registry to dynamically find the correct template path
    with a robust fallback mechanism.
    """

    def __init__(self, theme, default_theme):
        self.theme = theme
        self.default_theme = default_theme
        self._cache = {}

    def get_template_path(self, component_name: str) -> str:
        """
        Gets the resolved template path for a given layout component.
        The result is cached to improve performance.
        """
        if component_name == "header":
            logger.debug(f"--- Resolving '{component_name}' ---")
            logger.debug(f"Active Theme Slug: {self.theme.slug}")

        if component_name in self._cache:
            if component_name == "header":
                logger.debug(f"Returning cached path: {self._cache[component_name]}")
            return self._cache[component_name]

        if component_name not in LAYOUT_REGISTRY:
            # Fallback for unknown components to prevent errors
            fallback_path = f"themes/default/layouts/{component_name}/default.html"
            if component_name == "header":
                logger.debug(
                    f"Component not in registry, using fallback: {fallback_path}"
                )
            return fallback_path

        model_attr, subfolder = LAYOUT_REGISTRY[component_name]

        # 1. Get the selected layout name from the theme model
        layout_name = getattr(self.theme, model_attr, None)

        if component_name == "header":
            logger.debug(f"Theme's desired layout ('{model_attr}'): {layout_name}")

        if not layout_name:
            layout_name = getattr(self.default_theme, model_attr)
            if component_name == "header":
                logger.debug(
                    f"No layout set on theme, using default theme's layout: {layout_name}"
                )

        # 2. Generate template path candidates
        candidates = []
        subfolder_variants = [subfolder]
        if not subfolder.startswith("layouts/"):
            subfolder_variants.append(f"layouts/{subfolder}")

        # - Active theme path
        if self.theme and self.theme.theme_folder != "default":
            for variant in subfolder_variants:
                candidates.append(
                    f"themes/{self.theme.theme_folder}/{variant}/{layout_name}.html"
                )
        # - Default theme path (primary fallback)
        for variant in subfolder_variants:
            candidates.append(f"themes/default/{variant}/{layout_name}.html")

        if component_name == "header":
            logger.debug(f"Candidate Paths: {candidates}")

        # 3. Verify template existence and resolve
        resolved_path = None
        for candidate in candidates:
            if component_name == "header":
                logger.debug(f"Checking candidate: {candidate}")
            try:
                # Use get_template to verify existence. This is the correct way
                # to check if a template name is valid for inclusion.
                loader.get_template(candidate)
                resolved_path = candidate  # Return the valid template NAME
                if component_name == "header":
                    logger.debug(f"SUCCESS: Template found at '{candidate}'")
                break
            except loader.TemplateDoesNotExist:
                if component_name == "header":
                    logger.debug(f"FAILED: Template not found at '{candidate}'")
                continue

        if not resolved_path:
            # Final fallback to a known-good default if selection fails
            default_layout_name = getattr(self.default_theme, model_attr)
            resolved_path = f"themes/default/{subfolder}/{default_layout_name}.html"
            if component_name == "header":
                logger.debug(
                    f"No candidate found. Falling back to hardcoded default: {resolved_path}"
                )

        self._cache[component_name] = resolved_path

        if component_name == "header":
            logger.debug(f"Final resolved path: {resolved_path}")
            logger.debug(f"----------------------------------")

        return resolved_path


def get_theme_template_candidates(theme, component, layout_name):
    """
    Legacy function, now refactored to use the LayoutResolver for consistency.
    This function is kept for any parts of the system that might still use it,
    but new code should use the `layout_resolver` in the context.
    """
    if not theme:
        return []

    # This is a simplified version. For full functionality, a resolver instance is needed.
    # We will construct paths manually for backward compatibility.
    theme_folder = getattr(theme, "theme_folder", "default")

    # Determine the correct subfolder from the registry
    subfolder = f"layouts/{component}"
    for reg_component, (_, reg_subfolder) in LAYOUT_REGISTRY.items():
        if reg_component == component:
            subfolder = reg_subfolder
            break

    candidates = []
    if theme_folder and theme_folder != "default":
        candidates.append(f"themes/{theme_folder}/{subfolder}/{layout_name}.html")
    candidates.append(f"themes/default/{subfolder}/{layout_name}.html")
    return candidates


def get_theme_static_url(theme, asset_path):
    if not theme or not asset_path:
        return ""
    folder = (
        theme.get("theme_folder")
        if isinstance(theme, dict)
        else getattr(theme, "theme_folder", "")
    )
    slug = theme.get("slug") if isinstance(theme, dict) else getattr(theme, "slug", "")
    folder = folder or slug
    if not folder or folder == "default":
        return f"{settings.STATIC_URL}themes/default/{asset_path.lstrip('/')}"
    return f"/theme-assets/{folder}/{asset_path.lstrip('/')}"
