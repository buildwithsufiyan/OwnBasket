import tempfile
from pathlib import Path

from bs4 import BeautifulSoup
from django.test import SimpleTestCase, TestCase, override_settings

from themes.converter import (
    PRICE_PATTERN,
    analyze_html_file,
    apply_suggestion_to_file,
    backup_file,
    get_unique_selector,
    run_template_conversion,
)
from themes.models import TemplateConversionLog, Theme, ThemeFileBackup


class PricePatternTests(SimpleTestCase):
    def test_matches_common_currency_formats(self):
        for text in ("$19", "$1,299.00", "€ 45.50", "£9.99", "₹ 2,500"):
            with self.subTest(text=text):
                self.assertIsNotNone(PRICE_PATTERN.search(text))

    def test_ignores_amounts_without_currency_symbol(self):
        self.assertIsNone(PRICE_PATTERN.search("1299.00"))


class UniqueSelectorTests(SimpleTestCase):
    def test_returns_none_for_missing_tag(self):
        self.assertIsNone(get_unique_selector(None))

    def test_stops_at_nearest_id(self):
        soup = BeautifulSoup(
            "<div id='grid'><ul><li class='item'>A</li></ul></div>", "html.parser"
        )

        selector = get_unique_selector(soup.select_one("li"))

        self.assertEqual(selector, "#grid > ul:nth-of-type(1) > li.item:nth-of-type(1)")

    def test_includes_classes_and_sibling_position(self):
        soup = BeautifulSoup(
            "<div class='grid row'><span>A</span><span class='price'>$5</span></div>",
            "html.parser",
        )

        selector = get_unique_selector(soup.select_one("span.price"))

        self.assertEqual(
            selector, "div.grid.row:nth-of-type(1) > span.price:nth-of-type(2)"
        )

    def test_selector_resolves_back_to_the_same_element(self):
        soup = BeautifulSoup(
            "<section><div class='card'>A</div><div class='card'>B</div></section>",
            "html.parser",
        )
        target = soup.select("div.card")[1]

        self.assertIs(soup.select_one(get_unique_selector(target)), target)


class BackupFileTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file_path = Path(self.tmp.name) / "index.html"
        self.file_path.write_text("<html>v1</html>", encoding="utf-8")

    def test_creates_first_version(self):
        backup_path, version = backup_file(self.file_path)

        self.assertEqual(version, 1)
        self.assertEqual(backup_path.name, "index.v1.html")
        self.assertEqual(backup_path.parent.name, ".backups")
        self.assertEqual(backup_path.read_text(encoding="utf-8"), "<html>v1</html>")

    def test_increments_version_for_each_backup(self):
        backup_file(self.file_path)
        self.file_path.write_text("<html>v2</html>", encoding="utf-8")

        backup_path, version = backup_file(self.file_path)

        self.assertEqual(version, 2)
        self.assertEqual(backup_path.name, "index.v2.html")
        self.assertEqual(backup_path.read_text(encoding="utf-8"), "<html>v2</html>")


class ConverterDatabaseTestCase(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base_dir = Path(self.tmp.name)
        patcher = override_settings(BASE_DIR=self.base_dir)
        patcher.enable()
        self.addCleanup(patcher.disable)
        self.theme = Theme.objects.create(
            name="Aurora", slug="aurora", theme_folder="aurora"
        )
        self.theme_dir = self.base_dir / "themes" / "aurora"
        self.theme_dir.mkdir(parents=True)

    def write_template(self, name, html):
        path = self.theme_dir / name
        path.write_text(html, encoding="utf-8")
        return path


class AnalyzeHtmlFileTests(ConverterDatabaseTestCase):
    def test_creates_price_variable_suggestion(self):
        path = self.write_template(
            "index.html", "<div class='price'>$1,299.00</div>"
        )

        analyze_html_file(self.theme, path)

        suggestion = TemplateConversionLog.objects.get()
        self.assertEqual(suggestion.theme, self.theme)
        self.assertEqual(suggestion.file_path, "index.html")
        self.assertEqual(
            suggestion.conversion_type, TemplateConversionLog.ConversionType.VAR
        )
        self.assertEqual(suggestion.status, TemplateConversionLog.Status.PENDING)
        self.assertEqual(suggestion.confidence, 0.9)

    def test_price_outside_price_class_has_lower_confidence(self):
        path = self.write_template("index.html", "<span>$25</span>")

        analyze_html_file(self.theme, path)

        self.assertEqual(TemplateConversionLog.objects.get().confidence, 0.6)

    def test_prices_inside_script_are_ignored(self):
        path = self.write_template(
            "index.html", "<script>var total = '$25';</script>"
        )

        analyze_html_file(self.theme, path)

        self.assertFalse(TemplateConversionLog.objects.exists())

    def test_repeated_cards_create_single_wrap_suggestion(self):
        cards = "".join(f"<div class='card'>Item {i}</div>" for i in range(4))
        path = self.write_template("grid.html", f"<section id='grid'>{cards}</section>")

        analyze_html_file(self.theme, path)

        suggestion = TemplateConversionLog.objects.get(
            conversion_type=TemplateConversionLog.ConversionType.WRAP
        )
        self.assertEqual(suggestion.target_selector, "#grid")
        self.assertEqual(suggestion.confidence, 0.75)
        self.assertIn("{% for product in products %}", suggestion.suggested_code)

    def test_two_repeated_items_are_not_treated_as_a_grid(self):
        path = self.write_template(
            "grid.html", "<section><div class='card'>A</div><div class='card'>B</div></section>"
        )

        analyze_html_file(self.theme, path)

        self.assertFalse(
            TemplateConversionLog.objects.filter(
                conversion_type=TemplateConversionLog.ConversionType.WRAP
            ).exists()
        )

    def test_reanalysis_replaces_pending_suggestions_only(self):
        path = self.write_template("index.html", "<span>$25</span>")
        analyze_html_file(self.theme, path)
        TemplateConversionLog.objects.update(
            status=TemplateConversionLog.Status.REJECTED
        )

        analyze_html_file(self.theme, path)

        self.assertEqual(TemplateConversionLog.objects.count(), 2)
        analyze_html_file(self.theme, path)
        self.assertEqual(TemplateConversionLog.objects.count(), 2)

    def test_unreadable_file_is_skipped(self):
        analyze_html_file(self.theme, self.theme_dir / "missing.html")

        self.assertFalse(TemplateConversionLog.objects.exists())


class RunTemplateConversionTests(ConverterDatabaseTestCase):
    def test_analyzes_every_top_level_html_file(self):
        self.write_template("index.html", "<span>$10</span>")
        self.write_template("about.html", "<span>$20</span>")

        run_template_conversion(self.theme)

        self.assertEqual(
            sorted(
                TemplateConversionLog.objects.values_list("file_path", flat=True)
            ),
            ["about.html", "index.html"],
        )

    def test_missing_theme_directory_is_a_no_op(self):
        theme = Theme.objects.create(
            name="Ghost", slug="ghost", theme_folder="ghost"
        )

        run_template_conversion(theme)

        self.assertFalse(TemplateConversionLog.objects.exists())


class ApplySuggestionToFileTests(ConverterDatabaseTestCase):
    def build_suggestion(self, **overrides):
        payload = {
            "theme": self.theme,
            "file_path": "index.html",
            "target_selector": "span.price:nth-of-type(1)",
            "conversion_type": TemplateConversionLog.ConversionType.VAR,
            "original_html": "",
            "suggested_code": "<span class='price'>{{ product.price }}</span>",
        }
        payload.update(overrides)
        return TemplateConversionLog.objects.create(**payload)

    def test_missing_file_raises(self):
        suggestion = self.build_suggestion(file_path="missing.html")

        with self.assertRaises(FileNotFoundError):
            apply_suggestion_to_file(suggestion)

    def test_missing_target_element_raises_conflict(self):
        self.write_template("index.html", "<div>no price here</div>")
        suggestion = self.build_suggestion()

        with self.assertRaisesMessage(ValueError, "Target element not found"):
            apply_suggestion_to_file(suggestion)

    def test_var_suggestion_replaces_element_and_records_backup(self):
        self.write_template("index.html", "<span class='price'>$25</span>")
        suggestion = self.build_suggestion()

        self.assertTrue(apply_suggestion_to_file(suggestion))

        content = (self.theme_dir / "index.html").read_text(encoding="utf-8")
        self.assertIn("{{ product.price }}", content)
        self.assertNotIn("$25", content)
        backup = ThemeFileBackup.objects.get()
        self.assertEqual(backup.version, 1)
        self.assertEqual(backup.file_path, "index.html")
        self.assertEqual(
            (self.base_dir / backup.backup_file_path).read_text(encoding="utf-8"),
            "<span class='price'>$25</span>",
        )

    def test_wrap_suggestion_collapses_repeated_items_into_loop(self):
        cards = "".join(f"<div class='card'>Item {i}</div>" for i in range(3))
        self.write_template("grid.html", f"<section id='grid'>{cards}</section>")
        suggestion = self.build_suggestion(
            file_path="grid.html",
            target_selector="#grid",
            conversion_type=TemplateConversionLog.ConversionType.WRAP,
        )

        apply_suggestion_to_file(suggestion)

        content = (self.theme_dir / "grid.html").read_text(encoding="utf-8")
        self.assertIn("{% for product in products %}", content)
        self.assertIn("{% endfor %}", content)
        self.assertEqual(content.count("class=\"card\""), 1)

    def test_wrap_suggestion_without_children_raises(self):
        self.write_template("grid.html", "<section id='grid'></section>")
        suggestion = self.build_suggestion(
            file_path="grid.html",
            target_selector="#grid",
            conversion_type=TemplateConversionLog.ConversionType.WRAP,
        )

        with self.assertRaisesMessage(ValueError, "wrapper element has no children"):
            apply_suggestion_to_file(suggestion)

    def test_unsupported_conversion_type_raises(self):
        self.write_template("index.html", "<span class='price'>$25</span>")
        suggestion = self.build_suggestion(
            conversion_type=TemplateConversionLog.ConversionType.IMAGE
        )

        with self.assertRaises(NotImplementedError):
            apply_suggestion_to_file(suggestion)
