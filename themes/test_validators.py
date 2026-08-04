import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from themes.validators import (
    THEME_REQUIRED_DIRS,
    _is_js_framework_theme,
    _load_metadata,
    _resolve_preview_path,
    validate_ownbasket_theme,
    validate_static_theme,
)


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class LoadMetadataTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.theme_dir = Path(self.tmp.name) / "aurora"
        self.theme_dir.mkdir()

    def test_missing_theme_json_reports_error(self):
        metadata, errors = _load_metadata(self.theme_dir)

        self.assertEqual(metadata, {})
        self.assertEqual(errors, ["Missing theme.json in aurora."])

    def test_invalid_json_reports_error(self):
        (self.theme_dir / "theme.json").write_text("{not-json", encoding="utf-8")

        metadata, errors = _load_metadata(self.theme_dir)

        self.assertEqual(metadata, {})
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("Invalid theme.json:"))

    def test_valid_json_is_returned(self):
        write_json(self.theme_dir / "theme.json", {"name": "Aurora"})

        metadata, errors = _load_metadata(self.theme_dir)

        self.assertEqual(metadata, {"name": "Aurora"})
        self.assertEqual(errors, [])


class ResolvePreviewPathTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.theme_dir = Path(self.tmp.name)

    def test_returns_none_when_no_preview_exists(self):
        self.assertIsNone(_resolve_preview_path(self.theme_dir, {}))

    def test_prefers_metadata_declared_preview(self):
        (self.theme_dir / "assets").mkdir()
        declared = self.theme_dir / "assets" / "shot.png"
        declared.write_bytes(b"png")
        (self.theme_dir / "preview.jpg").write_bytes(b"jpg")

        resolved = _resolve_preview_path(
            self.theme_dir, {"preview_image": "assets/shot.png"}
        )

        self.assertEqual(resolved, declared)

    def test_falls_back_to_default_names(self):
        expected = self.theme_dir / "preview.png"
        expected.write_bytes(b"png")

        resolved = _resolve_preview_path(
            self.theme_dir, {"preview_image": "missing.png"}
        )

        self.assertEqual(resolved, expected)

    def test_ignores_directory_named_like_preview(self):
        (self.theme_dir / "preview.jpg").mkdir()

        self.assertIsNone(_resolve_preview_path(self.theme_dir, {}))


class JsFrameworkDetectionTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.theme_dir = Path(self.tmp.name)

    def test_no_package_json(self):
        self.assertFalse(_is_js_framework_theme(self.theme_dir))

    def test_react_dependency(self):
        write_json(
            self.theme_dir / "package.json", {"dependencies": {"react": "19.0.0"}}
        )

        self.assertTrue(_is_js_framework_theme(self.theme_dir))

    def test_next_dev_dependency(self):
        write_json(
            self.theme_dir / "package.json", {"devDependencies": {"next": "15.0.0"}}
        )

        self.assertTrue(_is_js_framework_theme(self.theme_dir))

    def test_plain_package_json_is_not_a_framework(self):
        write_json(
            self.theme_dir / "package.json", {"dependencies": {"bootstrap": "5.3.0"}}
        )

        self.assertFalse(_is_js_framework_theme(self.theme_dir))

    def test_broken_package_json_is_ignored(self):
        (self.theme_dir / "package.json").write_text("{", encoding="utf-8")

        self.assertFalse(_is_js_framework_theme(self.theme_dir))


class ValidateOwnbasketThemeTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.theme_dir = Path(self.tmp.name) / "aurora"
        self.theme_dir.mkdir()

    def build_complete_theme(self, metadata=None):
        payload = {
            "name": "Aurora",
            "slug": "aurora",
            "version": "1.0",
            "author": "OwnBasket",
            "description": "Aurora theme",
        }
        payload.update(metadata or {})
        write_json(self.theme_dir / "theme.json", payload)
        for dirname in THEME_REQUIRED_DIRS:
            (self.theme_dir / dirname).mkdir(parents=True, exist_ok=True)
        (self.theme_dir / "preview.jpg").write_bytes(b"jpg")

    def test_valid_theme_has_no_errors_or_warnings(self):
        self.build_complete_theme()

        metadata, errors, warnings = validate_ownbasket_theme(self.theme_dir)

        self.assertEqual(metadata["slug"], "aurora")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_metadata_errors_short_circuit_structure_checks(self):
        metadata, errors, warnings = validate_ownbasket_theme(self.theme_dir)

        self.assertEqual(metadata, {})
        self.assertEqual(errors, ["Missing theme.json in aurora."])
        self.assertEqual(warnings, [])

    def test_missing_fields_directories_and_preview_are_reported(self):
        write_json(self.theme_dir / "theme.json", {"name": "Aurora"})

        _, errors, _ = validate_ownbasket_theme(self.theme_dir)

        for field in ("slug", "version", "author", "description"):
            self.assertIn(f"theme.json missing required field: {field}.", errors)
        for dirname in THEME_REQUIRED_DIRS:
            self.assertIn(f"Missing required directory: {dirname}/", errors)
        self.assertTrue(any("Missing preview image" in error for error in errors))

    def test_slug_mismatch_is_a_warning_not_an_error(self):
        self.build_complete_theme({"slug": "northern-lights"})

        _, errors, warnings = validate_ownbasket_theme(self.theme_dir)

        self.assertEqual(errors, [])
        self.assertEqual(
            warnings,
            [
                "Folder name 'aurora' differs from theme.json slug 'northern-lights'."
            ],
        )

    def test_slug_is_derived_from_name_when_absent(self):
        self.build_complete_theme({"slug": "", "name": "Aurora Deluxe"})

        _, errors, warnings = validate_ownbasket_theme(self.theme_dir)

        self.assertIn("theme.json missing required field: slug.", errors)
        self.assertEqual(
            warnings,
            ["Folder name 'aurora' differs from theme.json slug 'aurora-deluxe'."],
        )


class ValidateStaticThemeTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.theme_dir = Path(self.tmp.name) / "my_static-theme"
        self.theme_dir.mkdir()

    def test_js_framework_theme_is_rejected(self):
        write_json(
            self.theme_dir / "package.json", {"dependencies": {"react": "19.0.0"}}
        )
        (self.theme_dir / "index.html").write_text("<html></html>", encoding="utf-8")

        metadata, errors, warnings = validate_static_theme(self.theme_dir)

        self.assertEqual(metadata, {})
        self.assertEqual(warnings, [])
        self.assertTrue(any("JavaScript-based project" in error for error in errors))
        self.assertFalse((self.theme_dir / "theme.json").exists())

    def test_theme_without_html_is_rejected(self):
        (self.theme_dir / "styles.css").write_text("body{}", encoding="utf-8")

        metadata, errors, _ = validate_static_theme(self.theme_dir)

        self.assertEqual(metadata, {})
        self.assertTrue(any("does not contain any HTML files" in e for e in errors))

    def test_generates_and_writes_placeholder_metadata(self):
        nested = self.theme_dir / "pages"
        nested.mkdir()
        (nested / "home.html").write_text("<html></html>", encoding="utf-8")

        metadata, errors, warnings = validate_static_theme(self.theme_dir, "Pack.zip")

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(metadata["name"], "My Static Theme")
        self.assertEqual(metadata["slug"], "my-static-theme")
        self.assertEqual(metadata["version"], "1.0")
        self.assertEqual(metadata["author"], "Imported")
        self.assertTrue(metadata["is_static_import"])
        written = json.loads((self.theme_dir / "theme.json").read_text(encoding="utf-8"))
        self.assertEqual(written, metadata)
