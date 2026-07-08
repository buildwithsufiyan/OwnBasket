import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.text import slugify

# These are the original, strict validation constants for OwnBasket themes.
THEME_REQUIRED_DIRS = (
    "templates",
    "templates/sections",
    "static",
    "static/css",
    "static/js",
    "static/images",
)
THEME_REQUIRED_METADATA = ("name", "slug", "version", "author", "description")
DEFAULT_PREVIEW_NAMES = ("preview.jpg", "preview.jpeg", "preview.png", "preview.webp")


def _load_metadata(theme_dir: Path) -> tuple[dict, list[str]]:
    """Loads theme.json from a directory."""
    metadata_path = theme_dir / "theme.json"
    if not metadata_path.exists():
        return {}, [f"Missing theme.json in {theme_dir.name}."]
    try:
        with metadata_path.open("r", encoding="utf-8") as f:
            return json.load(f), []
    except json.JSONDecodeError as exc:
        return {}, [f"Invalid theme.json: {exc}."]
    except OSError as exc:
        return {}, [f"Cannot read theme.json: {exc}."]


def _resolve_preview_path(theme_dir: Path, metadata: dict) -> Path | None:
    """Finds the preview image for a theme."""
    preview_value = (
        metadata.get("preview_image")
        or metadata.get("preview")
        or metadata.get("screenshot")
    )
    candidates = []
    if preview_value:
        candidates.append(theme_dir / str(preview_value))
    candidates.extend(theme_dir / name for name in DEFAULT_PREVIEW_NAMES)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _is_js_framework_theme(theme_root: Path) -> bool:
    """Checks for indicators of a JS framework like React or Next.js."""
    package_json_path = theme_root / "package.json"
    if not package_json_path.exists():
        return False
    try:
        with package_json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            dependencies = data.get("dependencies", {})
            dev_dependencies = data.get("devDependencies", {})
            if "react" in dependencies or "react" in dev_dependencies:
                return True
            if "next" in dependencies or "next" in dev_dependencies:
                return True
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass  # Ignore broken package.json
    return False


def validate_ownbasket_theme(
    theme_dir: Path,
) -> tuple[dict, list[str], list[str]]:
    """
    The original, strict validator for native OwnBasket themes.
    """
    metadata, errors = _load_metadata(theme_dir)
    warnings = []

    if errors:
        return metadata, errors, warnings

    for required_field in THEME_REQUIRED_METADATA:
        if not metadata.get(required_field):
            errors.append(f"theme.json missing required field: {required_field}.")

    for dirname in THEME_REQUIRED_DIRS:
        if not (theme_dir / dirname).is_dir():
            errors.append(f"Missing required directory: {dirname}/")

    if not _resolve_preview_path(theme_dir, metadata):
        errors.append(
            "Missing preview image. Add preview.jpg or set 'preview_image' in theme.json."
        )

    declared_slug = metadata.get("slug") or slugify(metadata.get("name") or "")
    if declared_slug and declared_slug != theme_dir.name:
        warnings.append(
            f"Folder name '{theme_dir.name}' differs from theme.json slug '{declared_slug}'."
        )

    return metadata, errors, warnings


def validate_static_theme(
    theme_dir: Path, original_filename: str = "theme.zip"
) -> tuple[dict, list[str], list[str]]:
    """
    A lenient validator for generic HTML/Bootstrap themes.
    """
    errors, warnings = [], []
    metadata = {}

    # 1. Check for JS frameworks, which are not supported
    if _is_js_framework_theme(theme_dir):
        errors.append(
            "This appears to be a React, Next.js, or other JavaScript-based project. "
            "Only static HTML/Bootstrap themes are supported for automatic conversion."
        )
        return {}, errors, warnings

    # 2. Check for at least one HTML file
    if not any(theme_dir.glob("**/*.html")):
        errors.append(
            "The uploaded ZIP does not contain any HTML files, so it cannot be imported."
        )
        return {}, errors, warnings

    # 3. Generate placeholder metadata
    theme_name = (
        (theme_dir.name or Path(original_filename).stem or "Imported Theme")
        .replace("-", " ")
        .replace("_", " ")
        .title()
    )
    metadata = {
        "name": theme_name,
        "slug": slugify(theme_name),
        "version": "1.0",
        "author": "Imported",
        "description": f"A static HTML theme '{theme_name}' automatically imported.",
        "is_static_import": True,
    }

    # 4. Write the generated theme.json to the directory
    try:
        with (theme_dir / "theme.json").open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
    except OSError as exc:
        errors.append(f"Could not write temporary theme.json: {exc}")

    return metadata, errors, warnings
