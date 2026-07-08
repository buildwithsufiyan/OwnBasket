from django.template import Context
from django.test import RequestFactory, TestCase

from themes.templatetags.theme_tags import render_header


class ThemeTagRegressionTests(TestCase):
    def test_render_header_uses_layout_resolver(self):
        class DummyResolver:
            def get_template_path(self, component_name):
                return "themes/default/header/header1.html"

        request = RequestFactory().get("/")
        context = Context({"layout_resolver": DummyResolver(), "request": request})

        output = render_header(context)

        self.assertIn("own-navbar", output)
