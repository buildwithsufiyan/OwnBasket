from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import ManagedFont, ManagedFontPack, ManagedFontPackFont
from .services import (
    bootstrap_typography_catalog,
    get_active_font_entries,
    get_designer_font_library_entries,
    get_font_pack_entries,
)


class ManagedFontModelTests(TestCase):
    def test_active_upload_font_requires_file(self):
        font = ManagedFont(
            name='Brittany Upload',
            css_name='Brittany Upload',
            category='script',
            source='upload',
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            font.full_clean()

    def test_active_google_font_does_not_require_file(self):
        font = ManagedFont(
            name='Inter Clone',
            css_name='Inter Clone',
            google_family='Inter',
            category='sans-serif',
            source='google',
            is_active=True,
        )

        font.full_clean()

    def test_font_upload_path_uses_media_fonts_directory(self):
        font = ManagedFont.objects.create(
            name='Shadow Uploaded',
            css_name='Shadow Uploaded',
            category='display',
            source='upload',
            is_active=False,
            font_file=SimpleUploadedFile('shadow.woff2', b'font-bytes', content_type='font/woff2'),
        )

        self.assertTrue(font.font_file.name.startswith('fonts/'))


class ManagedFontApiTests(TestCase):
    def setUp(self):
        bootstrap_typography_catalog()

    def test_active_fonts_api_excludes_inactive_fonts_and_returns_sorted_results(self):
        ManagedFont.objects.create(
            name='ZZ Inactive Upload',
            css_name='ZZ Inactive Upload',
            category='display',
            source='upload',
            is_active=False,
            font_file=SimpleUploadedFile('inactive.woff2', b'font-bytes', content_type='font/woff2'),
        )
        uploaded_font = ManagedFont.objects.create(
            name='Aardvark Upload',
            css_name='Aardvark Upload',
            category='sans-serif',
            source='upload',
            is_active=True,
            font_file=SimpleUploadedFile('aardvark.woff2', b'font-bytes', content_type='font/woff2'),
        )

        response = self.client.get(reverse('fonts:active-fonts-api'))
        payload = response.json()
        names = [entry['name'] for entry in payload['results']]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['pack'], 'all-fonts')
        self.assertEqual(names, sorted(names, key=str.lower))
        self.assertIn('Aardvark Upload', names)
        self.assertIn('Inter', names)
        self.assertNotIn('ZZ Inactive Upload', names)
        uploaded_entry = next(entry for entry in payload['results'] if entry['name'] == 'Aardvark Upload')
        self.assertEqual(uploaded_entry['font_url'], reverse('fonts:font-file', args=[uploaded_font.pk]))

    def test_active_fonts_api_filters_by_pack(self):
        response = self.client.get(reverse('fonts:active-fonts-api'), {'pack': 'e-commerce'})
        payload = response.json()
        names = [entry['name'] for entry in payload['results']]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['pack'], 'e-commerce')
        self.assertIn('Inter', names)
        self.assertIn('Outfit', names)
        self.assertNotIn('Playfair Display', names)

    def test_active_fonts_api_filters_by_designer_library(self):
        response = self.client.get(reverse('fonts:active-fonts-api'), {'designer': 'signature'})
        payload = response.json()
        names = [entry['name'] for entry in payload['results']]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['designer'], 'signature')
        self.assertIn('Great Vibes', names)
        self.assertIn('Sacramento', names)
        self.assertNotIn('Orbitron', names)

    def test_active_fonts_api_supports_combined_pack_and_designer_filters(self):
        response = self.client.get(
            reverse('fonts:active-fonts-api'),
            {'pack': 'banner-fonts', 'designer': 'tech'},
        )
        payload = response.json()
        names = [entry['name'] for entry in payload['results']]

        self.assertEqual(response.status_code, 200)
        self.assertIn('Exo 2', names)
        self.assertIn('Rajdhani', names)
        self.assertNotIn('Audiowide', names)
        self.assertNotIn('Inter', names)

    def test_get_active_font_entries_preserves_saved_legacy_value_with_pack_filter(self):
        entries = get_active_font_entries(
            current_values=['Custom Legacy Font'],
            pack_slug='business',
        )
        css_names = [entry['css_name'] for entry in entries]

        self.assertIn('Inter', css_names)
        self.assertIn('Custom Legacy Font', css_names)

    def test_font_stylesheet_generates_font_face_rules_for_upload_fonts_only(self):
        font = ManagedFont.objects.create(
            name='Chewy Uploaded',
            css_name='Chewy Uploaded',
            category='display',
            source='upload',
            is_active=True,
            font_file=SimpleUploadedFile('chewy.woff2', b'font-bytes', content_type='font/woff2'),
        )

        response = self.client.get(reverse('fonts:stylesheet'))
        css = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("@font-face {", css)
        self.assertIn("font-family: 'Chewy Uploaded';", css)
        self.assertIn(reverse('fonts:font-file', args=[font.pk]), css)
        self.assertIn("format('woff2')", css)
        self.assertNotIn("font-family: 'Inter';", css)

    def test_font_file_endpoint_sets_cache_headers_for_uploaded_fonts(self):
        font = ManagedFont.objects.create(
            name='Chewy Cached',
            css_name='Chewy Cached',
            category='display',
            source='upload',
            is_active=True,
            font_file=SimpleUploadedFile('chewy-cache.woff2', b'font-bytes', content_type='font/woff2'),
        )

        response = self.client.get(reverse('fonts:font-file', args=[font.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('max-age=31536000', response['Cache-Control'])

    def test_font_file_endpoint_rejects_google_fonts(self):
        google_font = ManagedFont.objects.get(name='Inter')

        response = self.client.get(reverse('fonts:font-file', args=[google_font.pk]))

        self.assertEqual(response.status_code, 404)


class SeedDefaultFontsCommandTests(TestCase):
    def test_seed_default_fonts_command_is_idempotent_for_typography_catalog(self):
        call_command('seed_default_fonts')
        call_command('seed_default_fonts')

        self.assertTrue(ManagedFont.objects.filter(name='Brittany').exists())
        self.assertTrue(ManagedFont.objects.filter(name='Inter', source='google', is_active=True).exists())
        self.assertTrue(ManagedFont.objects.filter(name='Geist', source='google', is_active=True).exists())
        self.assertTrue(ManagedFontPack.objects.filter(slug='all-fonts', is_active=True).exists())
        self.assertFalse(ManagedFontPack.objects.filter(slug='wedding', is_active=True).exists())
        self.assertEqual(ManagedFont.objects.filter(name='Inter').count(), 1)


class ManagedFontPackTests(TestCase):
    def setUp(self):
        bootstrap_typography_catalog()

    def test_default_pack_seed_and_assignment_populate_requested_pack_relations(self):
        self.assertTrue(ManagedFontPack.objects.filter(slug='business', is_active=True).exists())
        self.assertTrue(ManagedFontPackFont.objects.filter(font__name='Inter', pack__slug='business').exists())
        self.assertTrue(ManagedFontPackFont.objects.filter(font__name='Inter', pack__slug='e-commerce').exists())
        self.assertTrue(ManagedFontPackFont.objects.filter(font__name='Playfair Display', pack__slug='real-estate').exists())

    def test_pack_entries_return_only_current_curated_groups(self):
        entries = get_font_pack_entries()
        slugs = [entry['slug'] for entry in entries]

        self.assertIn('all-fonts', slugs)
        self.assertIn('popular-fonts', slugs)
        self.assertIn('e-commerce', slugs)
        self.assertNotIn('wedding', slugs)

    def test_designer_library_entries_return_curated_categories(self):
        entries = get_designer_font_library_entries()
        slugs = [entry['slug'] for entry in entries]

        self.assertIn('all-designer-fonts', slugs)
        self.assertIn('modern-sans', slugs)
        self.assertIn('signature', slugs)
        self.assertIn('monospace', slugs)
