from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from fonts.forms import ManagedFontAdminForm
from fonts.models import ManagedFont


def woff2_upload(name='zeta-test-sans.woff2'):
    return SimpleUploadedFile(name, b'wOF2' + b'\x00' * 64, content_type='font/woff2')


class ManagedFontAdminFormTests(TestCase):
    def base_data(self, **overrides):
        data = {
            'name': 'Zeta Test Sans',
            'css_name': 'Zeta Test Sans',
            'source': 'google',
            'google_family': 'Zeta Test Sans Display',
            'style_label': 'Script',
            'category': 'script',
            'is_active': True,
            'sort_order': 0,
        }
        data.update(overrides)
        return data

    def test_help_texts_are_attached_to_fields(self):
        form = ManagedFontAdminForm()

        self.assertIn('WOFF2 is preferred', form.fields['font_file'].help_text)
        self.assertIn('Optional preview image', form.fields['preview_image'].help_text)
        self.assertIn('font-family', form.fields['css_name'].help_text)
        self.assertIn('Google Font', form.fields['source'].help_text)
        self.assertIn('CSS Font Family Name', form.fields['google_family'].help_text)
        self.assertIn('Short descriptor', form.fields['style_label'].help_text)
        self.assertEqual(
            form.fields['sort_order'].help_text,
            'Lower numbers appear first in the picker.',
        )

    def test_valid_google_font_is_saved(self):
        form = ManagedFontAdminForm(data=self.base_data())

        self.assertTrue(form.is_valid(), form.errors)
        font = form.save()
        self.assertEqual(font.name, 'Zeta Test Sans')
        self.assertEqual(font.css_name, 'Zeta Test Sans')

    def test_name_is_stripped(self):
        form = ManagedFontAdminForm(data=self.base_data(name='  Zeta Test Sans  '))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['name'], 'Zeta Test Sans')

    def test_duplicate_name_is_rejected_case_insensitively(self):
        ManagedFont.objects.create(
            name='Zeta Test Sans', css_name='Zeta Test Sans', source='google'
        )

        form = ManagedFontAdminForm(data=self.base_data(name='zeta test sans'))

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['name'], ['A font with this name already exists.']
        )

    def test_duplicate_css_name_is_rejected(self):
        ManagedFont.objects.create(
            name='Zeta Test Sans', css_name='Zeta Test Sans', source='google'
        )

        form = ManagedFontAdminForm(
            data=self.base_data(name='Zeta Test Sans Two', css_name='zeta test sans')
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['css_name'],
            ['A font with this CSS font family name already exists.'],
        )

    def test_editing_a_font_keeps_its_own_name(self):
        font = ManagedFont.objects.create(
            name='Zeta Test Sans', css_name='Zeta Test Sans', source='google'
        )

        form = ManagedFontAdminForm(instance=font, data=self.base_data())

        self.assertTrue(form.is_valid(), form.errors)

    def test_css_name_is_required(self):
        form = ManagedFontAdminForm(data=self.base_data(css_name=''))

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['css_name'], ['This field is required.'])

    def test_disallowed_font_extension_is_rejected(self):
        form = ManagedFontAdminForm(
            data=self.base_data(source='upload'),
            files={'font_file': SimpleUploadedFile('zeta-test-sans.exe', b'MZ')},
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            'Only .ttf, .otf, .woff, and .woff2 files are allowed.',
            form.errors['font_file'],
        )

    def test_signature_mismatch_is_rejected(self):
        form = ManagedFontAdminForm(
            data=self.base_data(source='upload'),
            files={
                'font_file': SimpleUploadedFile(
                    'zeta-test-sans.woff2', b'FAKE' + b'\x00' * 64
                )
            },
        )

        self.assertFalse(form.is_valid())
        self.assertTrue(
            any('signature' in error for error in form.errors['font_file'])
        )

    def test_valid_font_upload_is_accepted(self):
        form = ManagedFontAdminForm(
            data=self.base_data(source='upload', google_family=''),
            files={'font_file': woff2_upload()},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNotNone(form.cleaned_data['font_file'])

    def test_missing_font_file_is_left_untouched(self):
        form = ManagedFontAdminForm(data=self.base_data())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['font_file'])
