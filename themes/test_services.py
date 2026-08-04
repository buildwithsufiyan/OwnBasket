import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from themes import services
from themes.models import Theme
from themes.services import (
    LayoutResolver,
    ThemeScanResult,
    ThemeUploadResult,
    _find_theme_root_and_type,
    _is_unsafe_zip_name,
    _metadata_to_theme_defaults,
    _safe_extract_zip,
    _unique_theme_folder,
    ensure_default_theme,
    get_active_theme,
    get_default_theme_payload,
    get_theme_static_url,
    get_theme_template_candidates,
    iter_theme_package_dirs,
)


class ResultDataclassTests(SimpleTestCase):
    def test_scan_result_is_valid_only_without_errors(self):
        path = Path("/tmp/aurora")

        self.assertTrue(ThemeScanResult(folder_name="aurora", path=path).is_valid)
        self.assertFalse(
            ThemeScanResult(folder_name="aurora", path=path, errors=["boom"]).is_valid
        )

    def test_upload_result_is_valid_only_without_errors(self):
        self.assertTrue(ThemeUploadResult().is_valid)
        self.assertFalse(ThemeUploadResult(errors=["boom"]).is_valid)


class UnsafeZipNameTests(SimpleTestCase):
    def test_safe_names(self):
        for name in ("index.html", "static/css/app.css", "nested/dir/", "a..b.html"):
            with self.subTest(name=name):
                self.assertFalse(_is_unsafe_zip_name(name))

    def test_unsafe_names(self):
        for name in (
            "/etc/passwd",
            "../evil.html",
            "theme/../../evil.html",
            "..\\evil.html",
            "install.exe",
            "setup.SH",
        ):
            with self.subTest(name=name):
                self.assertTrue(_is_unsafe_zip_name(name))


def build_zip(entries: dict[str, str]) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


class SafeExtractZipTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.destination = Path(self.tmp.name) / "extract"
        self.destination.mkdir()

    def test_extracts_safe_archive(self):
        with build_zip({"index.html": "<html></html>"}) as archive:
            _safe_extract_zip(archive, self.destination)

        self.assertEqual(
            (self.destination / "index.html").read_text(encoding="utf-8"),
            "<html></html>",
        )

    def test_rejects_traversal_member(self):
        with build_zip({"../evil.html": "x"}) as archive:
            with self.assertRaisesMessage(ValidationError, "Unsafe file in ZIP"):
                _safe_extract_zip(archive, self.destination)

        self.assertFalse((self.destination.parent / "evil.html").exists())

    def test_rejects_too_many_members(self):
        with build_zip({"index.html": "x"}) as archive:
            with self.settings():
                original = services.MAX_THEME_MEMBERS
                services.MAX_THEME_MEMBERS = 0
                self.addCleanup(setattr, services, "MAX_THEME_MEMBERS", original)
                with self.assertRaisesMessage(
                    ValidationError, "too many files"
                ):
                    _safe_extract_zip(archive, self.destination)

    def test_rejects_oversized_uncompressed_payload(self):
        with build_zip({"index.html": "x" * 100}) as archive:
            original = services.MAX_THEME_UNCOMPRESSED_BYTES
            services.MAX_THEME_UNCOMPRESSED_BYTES = 10
            self.addCleanup(
                setattr, services, "MAX_THEME_UNCOMPRESSED_BYTES", original
            )
            with self.assertRaisesMessage(ValidationError, "uncompressed size limit"):
                _safe_extract_zip(archive, self.destination)


class FindThemeRootAndTypeTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.extract_dir = Path(self.tmp.name)

    def test_detects_ownbasket_theme_by_metadata(self):
        nested = self.extract_dir / "pack" / "aurora"
        nested.mkdir(parents=True)
        (nested / "theme.json").write_text("{}", encoding="utf-8")

        root, theme_type = _find_theme_root_and_type(self.extract_dir)

        self.assertEqual(root, nested)
        self.assertEqual(theme_type, "ownbasket")

    def test_detects_javascript_project_at_root(self):
        (self.extract_dir / "package.json").write_text(
            json.dumps({"dependencies": {"next": "15.0.0"}}), encoding="utf-8"
        )
        (self.extract_dir / "index.html").write_text("<html></html>", encoding="utf-8")

        root, theme_type = _find_theme_root_and_type(self.extract_dir)

        self.assertEqual(root, self.extract_dir)
        self.assertEqual(theme_type, "javascript")

    def test_detects_javascript_project_in_subdirectory(self):
        nested = self.extract_dir / "app"
        nested.mkdir()
        (nested / "package.json").write_text(
            json.dumps({"dependencies": {"react": "19.0.0"}}), encoding="utf-8"
        )

        root, theme_type = _find_theme_root_and_type(self.extract_dir)

        self.assertEqual(root, nested)
        self.assertEqual(theme_type, "javascript")

    def test_static_root_is_directory_with_most_html_files(self):
        light = self.extract_dir / "docs"
        light.mkdir()
        (light / "readme.html").write_text("x", encoding="utf-8")
        heavy = self.extract_dir / "pages"
        heavy.mkdir()
        for name in ("index.html", "about.html", "shop.html"):
            (heavy / name).write_text("x", encoding="utf-8")

        root, theme_type = _find_theme_root_and_type(self.extract_dir)

        self.assertEqual(root, heavy)
        self.assertEqual(theme_type, "static")

    def test_archive_without_html_or_metadata_is_invalid(self):
        (self.extract_dir / "styles.css").write_text("body{}", encoding="utf-8")

        with self.assertRaisesMessage(ValidationError, "not a valid theme"):
            _find_theme_root_and_type(self.extract_dir)


class MetadataToThemeDefaultsTests(SimpleTestCase):
    def test_falls_back_to_folder_name_and_defaults(self):
        defaults = _metadata_to_theme_defaults({}, "my_theme")

        self.assertEqual(defaults["name"], "My Theme")
        self.assertEqual(defaults["slug"], "my_theme")
        self.assertEqual(defaults["theme_folder"], "my_theme")
        self.assertFalse(defaults["is_custom"])
        self.assertEqual(defaults["header_layout"], "header1")
        self.assertEqual(defaults["footer_layout"], "footer1")
        self.assertEqual(defaults["brand_primary_color"], "#ffb800")
        self.assertEqual(defaults["font_family"], "Inter")

    def test_supports_legacy_metadata_aliases(self):
        defaults = _metadata_to_theme_defaults(
            {
                "name": "Aurora",
                "header": "header3",
                "product_card": "card2",
                "primary_color": "#111111",
                "button_color": "#222222",
                "text_color": "#333333",
            },
            "aurora",
        )

        self.assertEqual(defaults["header_layout"], "header3")
        self.assertEqual(defaults["product_card_layout"], "card2")
        self.assertEqual(defaults["brand_primary_color"], "#111111")
        self.assertEqual(defaults["btn_primary_bg_color"], "#222222")
        self.assertEqual(defaults["text_primary_color"], "#333333")

    def test_explicit_values_win_over_aliases(self):
        defaults = _metadata_to_theme_defaults(
            {
                "slug": "Aurora Pro",
                "header_layout": "header2",
                "header": "header9",
                "brand_primary_color": "#abcdef",
                "primary_color": "#000000",
            },
            "aurora",
        )

        self.assertEqual(defaults["slug"], "aurora-pro")
        self.assertEqual(defaults["header_layout"], "header2")
        self.assertEqual(defaults["brand_primary_color"], "#abcdef")


class GetThemeStaticUrlTests(SimpleTestCase):
    def test_returns_empty_string_without_theme_or_path(self):
        self.assertEqual(get_theme_static_url(None, "css/app.css"), "")
        self.assertEqual(get_theme_static_url({"theme_folder": "aurora"}, ""), "")

    @override_settings(STATIC_URL="/static/")
    def test_default_theme_uses_static_url(self):
        self.assertEqual(
            get_theme_static_url({"theme_folder": "default"}, "/css/app.css"),
            "/static/themes/default/css/app.css",
        )

    @override_settings(STATIC_URL="/static/")
    def test_theme_without_folder_falls_back_to_default(self):
        self.assertEqual(
            get_theme_static_url({"slug": ""}, "css/app.css"),
            "/static/themes/default/css/app.css",
        )

    def test_custom_theme_uses_theme_assets_route(self):
        theme = Theme(theme_folder="aurora", slug="aurora")

        self.assertEqual(
            get_theme_static_url(theme, "/css/app.css"),
            "/theme-assets/aurora/css/app.css",
        )

    def test_slug_is_used_when_folder_is_missing(self):
        self.assertEqual(
            get_theme_static_url({"theme_folder": "", "slug": "aurora"}, "css/app.css"),
            "/theme-assets/aurora/css/app.css",
        )


class GetThemeTemplateCandidatesTests(SimpleTestCase):
    def test_returns_empty_list_without_theme(self):
        self.assertEqual(get_theme_template_candidates(None, "header", "header1"), [])

    def test_registered_component_uses_registry_subfolder(self):
        theme = Theme(theme_folder="aurora")

        self.assertEqual(
            get_theme_template_candidates(theme, "product_list", "card1"),
            [
                "themes/aurora/product_card/card1.html",
                "themes/default/product_card/card1.html",
            ],
        )

    def test_unknown_component_falls_back_to_layouts_folder(self):
        theme = Theme(theme_folder="default")

        self.assertEqual(
            get_theme_template_candidates(theme, "sidebar", "layout1"),
            ["themes/default/layouts/sidebar/layout1.html"],
        )


class LayoutResolverTests(SimpleTestCase):
    def setUp(self):
        self.default_theme = Theme(**get_default_theme_payload())

    def test_resolves_existing_default_template(self):
        resolver = LayoutResolver(self.default_theme, self.default_theme)

        self.assertEqual(
            resolver.get_template_path("header"), "themes/default/header/header1.html"
        )

    def test_result_is_cached(self):
        resolver = LayoutResolver(self.default_theme, self.default_theme)
        first = resolver.get_template_path("footer")
        resolver.theme = Theme(**{**get_default_theme_payload(), "footer_layout": "footer2"})

        self.assertEqual(resolver.get_template_path("footer"), first)

    def test_unknown_component_returns_generic_fallback(self):
        resolver = LayoutResolver(self.default_theme, self.default_theme)

        self.assertEqual(
            resolver.get_template_path("sidebar"),
            "themes/default/layouts/sidebar/default.html",
        )
        self.assertNotIn("sidebar", resolver._cache)

    def test_missing_layout_falls_back_to_default_theme_layout(self):
        theme = Theme(**{**get_default_theme_payload(), "header_layout": ""})
        resolver = LayoutResolver(theme, self.default_theme)

        self.assertEqual(
            resolver.get_template_path("header"), "themes/default/header/header1.html"
        )

    def test_unresolvable_layout_falls_back_to_default_theme_template(self):
        theme = Theme(
            **{
                **get_default_theme_payload(),
                "theme_folder": "aurora",
                "header_layout": "does-not-exist",
            }
        )
        resolver = LayoutResolver(theme, self.default_theme)

        self.assertEqual(
            resolver.get_template_path("header"), "themes/default/header/header1.html"
        )


class EnsureDefaultThemeTests(TestCase):
    def test_creates_default_theme_once(self):
        theme = ensure_default_theme()

        self.assertEqual(theme.slug, "default")
        self.assertEqual(theme.theme_folder, "default")
        self.assertEqual(ensure_default_theme().pk, theme.pk)
        self.assertEqual(Theme.objects.filter(slug="default").count(), 1)


class UniqueThemeFolderTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = override_settings(BASE_DIR=Path(self.tmp.name))
        patcher.enable()
        self.addCleanup(patcher.disable)

    def test_returns_slugified_base_name_when_free(self):
        self.assertEqual(_unique_theme_folder("Aurora Pro"), "aurora-pro")

    def test_falls_back_to_theme_for_empty_slug(self):
        self.assertEqual(_unique_theme_folder(""), "theme")

    def test_suffixes_when_directory_exists(self):
        (Path(self.tmp.name) / "themes" / "aurora").mkdir(parents=True)

        self.assertEqual(_unique_theme_folder("aurora"), "aurora-2")

    def test_suffixes_when_theme_record_exists(self):
        Theme.objects.create(name="Aurora", slug="aurora", theme_folder="aurora")

        self.assertEqual(_unique_theme_folder("aurora"), "aurora-2")


class IterThemePackageDirsTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.themes_root = Path(self.tmp.name) / "themes"
        patcher = override_settings(BASE_DIR=Path(self.tmp.name))
        patcher.enable()
        self.addCleanup(patcher.disable)

    def test_returns_empty_list_when_root_missing(self):
        self.assertEqual(iter_theme_package_dirs(), [])

    def test_skips_ignored_hidden_dirs_and_files(self):
        self.themes_root.mkdir()
        for name in ("Zephyr", "aurora", "__pycache__", "migrations", ".hidden"):
            (self.themes_root / name).mkdir()
        (self.themes_root / "services.py").write_text("", encoding="utf-8")

        self.assertEqual(
            [path.name for path in iter_theme_package_dirs()], ["aurora", "Zephyr"]
        )


class GetActiveThemeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.factory = RequestFactory()

    def build_request(self, session=None):
        request = self.factory.get("/")
        request.session = session or {}
        return request

    def test_falls_back_to_default_theme(self):
        theme = get_active_theme(self.build_request())

        self.assertEqual(theme.slug, "default")

    def test_returns_active_theme(self):
        active = Theme.objects.create(
            name="Aurora", slug="aurora", theme_folder="aurora", is_active=True
        )

        self.assertEqual(get_active_theme(self.build_request()).pk, active.pk)

    def test_preview_theme_overrides_active_theme(self):
        Theme.objects.create(
            name="Aurora", slug="aurora", theme_folder="aurora", is_active=True
        )
        preview = Theme.objects.create(
            name="Zephyr", slug="zephyr", theme_folder="zephyr"
        )

        resolved = get_active_theme(
            self.build_request({"preview_theme_id": preview.pk})
        )

        self.assertEqual(resolved.pk, preview.pk)

    def test_preview_data_is_applied_without_persisting(self):
        preview = Theme.objects.create(
            name="Zephyr", slug="zephyr", theme_folder="zephyr"
        )

        resolved = get_active_theme(
            self.build_request(
                {
                    "preview_theme_id": preview.pk,
                    "preview_theme_data": {"brand_primary_color": "#123456"},
                }
            )
        )

        self.assertEqual(resolved.brand_primary_color, "#123456")
        preview.refresh_from_db()
        self.assertNotEqual(preview.brand_primary_color, "#123456")

    def test_unknown_preview_id_falls_back_to_active_theme(self):
        active = Theme.objects.create(
            name="Aurora", slug="aurora", theme_folder="aurora", is_active=True
        )

        resolved = get_active_theme(self.build_request({"preview_theme_id": 9999}))

        self.assertEqual(resolved.pk, active.pk)


class InstallThemeZipTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = override_settings(BASE_DIR=Path(self.tmp.name))
        patcher.enable()
        self.addCleanup(patcher.disable)

    def upload(self, entries, name="theme.zip"):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for entry_name, content in entries.items():
                archive.writestr(entry_name, content)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/zip")

    def test_rejects_non_zip_filename(self):
        result = services.install_theme_zip(self.upload({}, name="theme.tar.gz"))

        self.assertEqual(result.errors, ["Only .zip theme uploads are allowed."])
        self.assertFalse(result.is_valid)

    def test_rejects_oversized_upload(self):
        upload = self.upload({"index.html": "x"})
        original = services.MAX_THEME_ZIP_BYTES
        services.MAX_THEME_ZIP_BYTES = 1
        self.addCleanup(setattr, services, "MAX_THEME_ZIP_BYTES", original)

        result = services.install_theme_zip(upload)

        self.assertEqual(result.errors, ["Theme ZIP is too large (max 50 MB)."])

    def test_rejects_file_that_is_not_a_zip(self):
        upload = SimpleUploadedFile("theme.zip", b"definitely-not-a-zip")

        result = services.install_theme_zip(upload)

        self.assertEqual(result.errors, ["Uploaded file is not a valid ZIP archive."])

    def test_rejects_javascript_project(self):
        result = services.install_theme_zip(
            self.upload(
                {
                    "package.json": json.dumps({"dependencies": {"react": "19.0.0"}}),
                    "index.html": "<html></html>",
                }
            )
        )

        self.assertTrue(any("React/Next.js" in error for error in result.errors))

    def test_rejects_unsafe_archive_member(self):
        result = services.install_theme_zip(self.upload({"../evil.html": "x"}))

        self.assertTrue(any("Unsafe file in ZIP" in error for error in result.errors))

    def test_installs_static_theme_and_creates_record(self):
        result = services.install_theme_zip(
            self.upload({"pages/index.html": "<html><body>Shop</body></html>"})
        )

        self.assertEqual(result.errors, [])
        self.assertTrue(result.is_static_import)
        self.assertEqual(result.folder_name, "pages")
        self.assertIsNotNone(result.theme)
        self.assertEqual(result.theme.theme_folder, "pages")
        installed = Path(self.tmp.name) / "themes" / "pages"
        self.assertTrue((installed / "index.html").is_file())
        self.assertTrue((installed / "theme.json").is_file())

    def test_installs_ownbasket_theme_with_full_structure(self):
        metadata = {
            "name": "Aurora",
            "slug": "aurora",
            "version": "2.0",
            "author": "QentraX",
            "description": "Aurora theme",
            "header_layout": "header2",
        }
        entries = {
            "aurora/theme.json": json.dumps(metadata),
            "aurora/preview.jpg": "jpg-bytes",
        }
        for dirname in (
            "templates",
            "templates/sections",
            "static",
            "static/css",
            "static/js",
            "static/images",
        ):
            entries[f"aurora/{dirname}/.keep"] = ""

        result = services.install_theme_zip(self.upload(entries))

        self.assertEqual(result.errors, [])
        self.assertFalse(result.is_static_import)
        self.assertEqual(result.theme.slug, "aurora")
        self.assertEqual(result.theme.version, "2.0")
        self.assertEqual(result.theme.header_layout, "header2")

    def test_invalid_ownbasket_theme_is_removed_after_install(self):
        result = services.install_theme_zip(
            self.upload({"aurora/theme.json": json.dumps({"name": "Aurora"})})
        )

        self.assertTrue(result.errors)
        self.assertFalse(Theme.objects.filter(slug="aurora").exists())
        self.assertFalse((Path(self.tmp.name) / "themes" / "aurora").exists())


class ScanThemePackagesTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.themes_root = Path(self.tmp.name) / "themes"
        self.themes_root.mkdir()
        patcher = override_settings(BASE_DIR=Path(self.tmp.name))
        patcher.enable()
        self.addCleanup(patcher.disable)

    def build_theme_dir(self, folder, metadata=None, complete=True):
        theme_dir = self.themes_root / folder
        theme_dir.mkdir()
        payload = {
            "name": folder.title(),
            "slug": folder,
            "version": "1.0",
            "author": "OwnBasket",
            "description": f"{folder} theme",
        }
        payload.update(metadata or {})
        (theme_dir / "theme.json").write_text(json.dumps(payload), encoding="utf-8")
        if complete:
            for dirname in (
                "templates",
                "templates/sections",
                "static",
                "static/css",
                "static/js",
                "static/images",
            ):
                (theme_dir / dirname).mkdir(parents=True, exist_ok=True)
            (theme_dir / "preview.jpg").write_bytes(b"jpg")
        return theme_dir

    def test_creates_themes_for_valid_packages(self):
        self.build_theme_dir("aurora")

        results = services.scan_theme_packages()

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertTrue(result.is_valid)
        self.assertTrue(result.created)
        self.assertFalse(result.updated)
        self.assertEqual(result.theme.theme_folder, "aurora")
        self.assertTrue(Theme.objects.filter(slug="default").exists())

    def test_rescan_updates_existing_theme(self):
        self.build_theme_dir("aurora")
        services.scan_theme_packages()
        shutil.rmtree(self.themes_root / "aurora")
        self.build_theme_dir("aurora", {"version": "3.0"})

        results = services.scan_theme_packages()

        self.assertFalse(results[0].created)
        self.assertTrue(results[0].updated)
        self.assertEqual(results[0].theme.version, "3.0")

    def test_invalid_package_is_reported_without_creating_theme(self):
        self.build_theme_dir("broken", complete=False)

        results = services.scan_theme_packages()

        self.assertFalse(results[0].is_valid)
        self.assertIsNone(results[0].theme)
        self.assertFalse(Theme.objects.filter(theme_folder="broken").exists())

    def test_validation_map_is_keyed_by_folder_name(self):
        self.build_theme_dir("aurora")
        self.build_theme_dir("broken", complete=False)

        validation_map = services.get_theme_validation_map()

        self.assertEqual(sorted(validation_map), ["aurora", "broken"])
        self.assertTrue(validation_map["aurora"].is_valid)
        self.assertFalse(validation_map["broken"].is_valid)
