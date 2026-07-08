import json
import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import IntegrityError, transaction
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
        "primary_color": "#ffb800",
        "secondary_color": "#232f3e",
        "accent_color": "#ffb800",
        "bg_color": "#f4f6f9",
        "text_color": "#1a1a1a",
        "border_color": "#eaecf0",
        "button_color": "#ffb800",
        "hover_color": "#e0a200",
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
    for member in zip_file.infolist():
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
        "primary_color": metadata.get("primary_color", "#ffb800"),
        "secondary_color": metadata.get("secondary_color", "#232f3e"),
        "accent_color": metadata.get("accent_color", "#ffb800"),
        "bg_color": metadata.get("bg_color", "#f4f6f9"),
        "text_color": metadata.get("text_color", "#1a1a1a"),
        "border_color": metadata.get("border_color", "#eaecf0"),
        "button_color": metadata.get("button_color", "#ffb800"),
        "hover_color": metadata.get("hover_color", "#e0a200"),
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


def get_theme_template_candidates(theme, component, layout_name):
    if not theme:
        return []

    slug = theme.get("slug") if isinstance(theme, dict) else getattr(theme, "slug", "")
    folder = (
        theme.get("theme_folder")
        if isinstance(theme, dict)
        else getattr(theme, "theme_folder", "")
    )

    candidates = []
    if folder and folder != "default":
        candidates.append(f"{folder}/templates/{component}/{layout_name}.html")
    if slug and slug != "default":
        candidates.append(f"themes/{slug}/{component}/{layout_name}.html")
    candidates.append(f"themes/default/{component}/{layout_name}.html")
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
