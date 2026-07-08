from pathlib import Path

from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from core.templatetags.ownbasket_fonts import ownbasket_google_fonts_url
from fonts.models import ManagedFont
from fonts.services import bootstrap_typography_catalog, get_active_font_entries

from .admin import BannerCarouselAdmin
from .forms import BannerCarouselAdminForm, HomepageSettingsAdminForm
from .models import BannerCarousel, HomepageCarousel


class BannerCarouselModelTest(TestCase):
    def test_active_banner_carousels_are_returned_in_display_order(self):
        first_slide = BannerCarousel.objects.create(
            badge_text='UP TO 50% OFF',
            heading='First Hero Slide',
            description='First hero content',
            button_text='Shop Now',
            button_url='https://example.com/first',
            layout_template='layout_2',
            display_order=2,
            is_active=True,
            slide_duration=6000,
            image=SimpleUploadedFile('hero-1.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )
        second_slide = BannerCarousel.objects.create(
            badge_text='NEW ARRIVALS',
            heading='Second Hero Slide',
            description='Second hero content',
            button_text='Explore',
            button_url='https://example.com/second',
            layout_template='layout_1',
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('hero-2.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )
        inactive_slide = BannerCarousel.objects.create(
            badge_text='INACTIVE',
            heading='Inactive Hero Slide',
            description='Inactive hero content',
            button_text='Hidden',
            button_url='https://example.com/inactive',
            layout_template='layout_3',
            display_order=0,
            is_active=False,
            slide_duration=4000,
            image=SimpleUploadedFile('hero-3.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('banner_carousels', response.context)
        self.assertEqual(
            list(response.context['banner_carousels']),
            [second_slide, first_slide],
        )
        self.assertNotIn(inactive_slide, response.context['banner_carousels'])

    def test_banner_carousel_str_uses_heading_when_available(self):
        slide = BannerCarousel.objects.create(
            badge_text='HOT DEAL',
            heading='Flash Sale',
            description='Flash sale details',
            button_text='See More',
            button_url='https://example.com/flash',
            layout_template='layout_3',
            display_order=1,
            is_active=True,
            slide_duration=7000,
            image=SimpleUploadedFile('flash.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        self.assertEqual(str(slide), 'Flash Sale')

    def test_banner_carousel_renders_predefined_layout_templates(self):
        cases = [
            ('layout_1', 'hero-layout-layout_1'),
            ('layout_2', 'hero-layout-layout_2'),
            ('layout_3', 'hero-layout-center'),
            ('layout_4', 'hero-layout-full'),
            ('layout_5', 'hero-layout-overlay-right'),
            ('layout_6', 'hero-layout-overlay-left'),
        ]

        for layout_template, expected_class in cases:
            with self.subTest(layout_template=layout_template):
                BannerCarousel.objects.create(
                    badge_text='FLASH SALE',
                    heading='Desktop Hero Banner',
                    description='Hero content for alignment testing',
                    button_text='Shop Now',
                    button_url='https://example.com/hero',
                    layout_template=layout_template,
                    display_order=1,
                    is_active=True,
                    slide_duration=5000,
                    image=SimpleUploadedFile('desktop.jpg', b'fake-image-bytes', content_type='image/jpeg'),
                )

                response = self.client.get(reverse('home'))
                html = response.content.decode()

                self.assertIn(expected_class, html)

    def test_duplicate_banner_copies_configurable_fields_and_image(self):
        slide = BannerCarousel.objects.create(
            badge_text='HOT DEAL',
            heading='Launch Banner',
            description='Hero copy for duplication',
            button_text='Shop Now',
            button_url='https://example.com/hero',
            layout_template='layout_3',
            button_variant='pill',
            background_type='gradient',
            show_on_mobile=False,
            views_count=4,
            clicks_count=1,
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('launch.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        duplicate = slide.duplicate()

        self.assertNotEqual(duplicate.pk, slide.pk)
        self.assertEqual(duplicate.heading, 'Launch Banner Copy')
        self.assertEqual(duplicate.button_variant, slide.button_variant)
        self.assertEqual(duplicate.background_type, slide.background_type)
        self.assertFalse(duplicate.show_on_mobile)
        self.assertEqual(duplicate.views_count, 0)
        self.assertEqual(duplicate.clicks_count, 0)
        self.assertTrue(duplicate.image.name)

    def test_banner_ctr_property_calculates_click_rate(self):
        slide = BannerCarousel.objects.create(
            badge_text='TRENDING',
            heading='Analytics Banner',
            description='Measuring clicks',
            button_text='View Deal',
            button_url='https://example.com/deal',
            layout_template='layout_1',
            views_count=20,
            clicks_count=5,
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('analytics.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        self.assertEqual(slide.ctr_percentage, 25.0)
        self.assertEqual(slide.ctr_display, '25.0%')

    def test_existing_banners_keep_overlay_enabled_by_default(self):
        slide = BannerCarousel.objects.create(
            badge_text='DEFAULT',
            heading='Overlay Default',
            description='Overlay should stay enabled for existing banners',
            button_text='Open',
            button_url='https://example.com/default',
            layout_template='layout_1',
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('default-overlay.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        self.assertTrue(slide.enable_overlay)

    def test_overlay_markup_is_not_rendered_when_overlay_is_disabled(self):
        BannerCarousel.objects.create(
            badge_text='PLAIN',
            heading='Overlay Off Banner',
            description='No overlay layer should render',
            button_text='View',
            button_url='https://example.com/plain',
            layout_template='layout_4',
            enable_overlay=False,
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('plain-banner.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        response = self.client.get(reverse('home'))
        html = response.content.decode()

        self.assertNotIn('<div class="hero-layout-overlay-layer"', html)

    def test_overlay_markup_renders_when_overlay_is_enabled(self):
        BannerCarousel.objects.create(
            badge_text='ON',
            heading='Overlay On Banner',
            description='Overlay layer should render',
            button_text='View',
            button_url='https://example.com/overlay-on',
            layout_template='layout_4',
            enable_overlay=True,
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('overlay-banner.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        response = self.client.get(reverse('home'))
        html = response.content.decode()

        self.assertIn('<div class="hero-layout-overlay-layer"', html)

    def test_admin_hides_overlay_fields_when_overlay_is_disabled(self):
        request = RequestFactory().get('/admin/')
        admin_instance = BannerCarouselAdmin(BannerCarousel, AdminSite())
        slide = BannerCarousel.objects.create(
            badge_text='ADMIN',
            heading='Admin Overlay Off',
            description='Overlay fields should be hidden after save',
            button_text='View',
            button_url='https://example.com/admin',
            layout_template='layout_1',
            enable_overlay=False,
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('admin-overlay-off.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        flattened_fields = []
        for _, options in admin_instance.get_fieldsets(request, slide):
            flattened_fields.extend(options.get('fields', ()))

        self.assertIn('enable_overlay', flattened_fields)
        self.assertNotIn('background_overlay_color', flattened_fields)
        self.assertNotIn('background_overlay_opacity', flattened_fields)

    def test_banner_click_tracking_increments_counter_and_redirects(self):
        slide = BannerCarousel.objects.create(
            badge_text='HOT DEAL',
            heading='Tracked Banner',
            description='Track click redirect',
            button_text='Shop Now',
            button_url='https://example.com/original',
            layout_template='layout_1',
            clicks_count=2,
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('tracked-click.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        response = self.client.get(
            reverse('track_banner_click', args=[slide.pk]),
            {'next': 'https://example.com/custom-destination'},
        )

        slide.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://example.com/custom-destination')
        self.assertEqual(slide.clicks_count, 3)

    def test_banner_view_tracking_only_updates_targeted_active_slide(self):
        tracked_slide = BannerCarousel.objects.create(
            badge_text='VISIBLE',
            heading='Tracked View',
            description='Track view impression',
            button_text='Open',
            button_url='https://example.com/viewed',
            layout_template='layout_1',
            views_count=4,
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('tracked-view.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )
        untouched_slide = BannerCarousel.objects.create(
            badge_text='SECOND',
            heading='Untouched View',
            description='Should remain same',
            button_text='Open',
            button_url='https://example.com/untouched',
            layout_template='layout_2',
            views_count=9,
            display_order=2,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('untouched-view.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        response = self.client.post(reverse('track_banner_view', args=[tracked_slide.pk]))

        tracked_slide.refresh_from_db()
        untouched_slide.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'tracked': True})
        self.assertEqual(tracked_slide.views_count, 5)
        self.assertEqual(untouched_slide.views_count, 9)

    def test_home_page_does_not_bulk_increment_banner_views(self):
        slide = BannerCarousel.objects.create(
            badge_text='STATIC',
            heading='No Bulk Increment',
            description='Homepage render should not inflate analytics',
            button_text='Read More',
            button_url='https://example.com/no-bulk',
            layout_template='layout_3',
            views_count=7,
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('no-bulk.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        response = self.client.get(reverse('home'))
        slide.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(slide.views_count, 7)

    def test_banner_font_family_fields_render_in_homepage_markup(self):
        slide = BannerCarousel.objects.create(
            badge_text='TYPO',
            heading='Typography Banner',
            description='Hero font families should be rendered.',
            button_text='Shop Fonts',
            button_url='https://example.com/fonts',
            layout_template='layout_1',
            badge_font_family='Poppins',
            heading_font_family='Playfair Display',
            description_font_family='DM Sans',
            button_font_family='Montserrat',
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('fonts.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        response = self.client.get(reverse('home'))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("font-family:'Poppins', sans-serif;", html)
        self.assertIn("font-family:'Playfair Display', sans-serif;", html)
        self.assertIn("font-family:'DM Sans', sans-serif;", html)
        self.assertIn("font-family:'Montserrat', sans-serif;", slide.button_css_style)


class HomepageCarouselModelTest(TestCase):
    def test_active_carousels_are_returned_in_display_order(self):
        first_slide = HomepageCarousel.objects.create(
            title='First Slide',
            redirect_url='https://example.com/first',
            display_order=2,
            is_active=True,
            slide_duration=6000,
            image=SimpleUploadedFile('first.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )
        second_slide = HomepageCarousel.objects.create(
            title='Second Slide',
            redirect_url='https://example.com/second',
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('second.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )
        inactive_slide = HomepageCarousel.objects.create(
            title='Inactive Slide',
            redirect_url='https://example.com/inactive',
            display_order=0,
            is_active=False,
            slide_duration=4000,
            image=SimpleUploadedFile('inactive.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('homepage_carousels', response.context)
        self.assertEqual(
            list(response.context['homepage_carousels']),
            [second_slide, first_slide],
        )
        self.assertNotIn(inactive_slide, response.context['homepage_carousels'])

    def test_carousel_str_uses_title_when_available(self):
        slide = HomepageCarousel.objects.create(
            title='Launch Sale',
            redirect_url='https://example.com/sale',
            display_order=1,
            is_active=True,
            slide_duration=7000,
            image=SimpleUploadedFile('sale.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        self.assertEqual(str(slide), 'Launch Sale')


class BannerAdminVisualEditorTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username='admin-visual-editor',
            email='admin@example.com',
            password='secret123',
        )
        bootstrap_typography_catalog()

    def test_banner_admin_form_uses_visual_editor_widgets_for_colors_and_sizes(self):
        ManagedFont.objects.create(
            name='Brusher Uploaded',
            css_name='Brusher Uploaded',
            category='script',
            source='upload',
            is_active=True,
            font_file=SimpleUploadedFile('brusher.woff2', b'fake-font', content_type='font/woff2'),
        )
        form = BannerCarouselAdminForm()

        self.assertIn('ve-color-source', form.fields['heading_text_color'].widget.attrs.get('class', ''))
        self.assertIn('ve-css-size', form.fields['heading_font_size'].widget.attrs.get('class', ''))
        self.assertIn('ve-css-padding', form.fields['button_padding'].widget.attrs.get('class', ''))
        self.assertIn('ve-dimension-input', form.fields['button_width'].widget.attrs.get('class', ''))
        self.assertIn('ve-searchable-select', form.fields['background_position'].widget.attrs.get('class', ''))
        self.assertIn('ve-searchable-select', form.fields['heading_font_family'].widget.attrs.get('class', ''))
        self.assertIn('ve-searchable-select', form.fields['button_font_family'].widget.attrs.get('class', ''))
        self.assertEqual(form.fields['layout_template'].widget.attrs.get('data-dropdown'), 'banner-layout')
        self.assertIn(('Brusher Uploaded', 'Brusher Uploaded'), form.fields['heading_font_family'].choices)
        self.assertIn(('Inter', 'Inter'), form.fields['button_font_family'].choices)
        self.assertEqual(len(form.fields['layout_template'].choices), 7)
        self.assertIn(('layout_7', 'Layout 7 = Split Text + Center Image'), form.fields['layout_template'].choices)
        self.assertEqual(form.fields['heading_font_family'].widget.attrs.get('data-font-preview'), 'true')
        self.assertEqual(form.fields['button_font_family'].widget.attrs.get('data-font-preview'), 'true')
        widget_context = form.fields['heading_font_family'].widget.get_context(
            'heading_font_family',
            None,
            {'id': 'id_heading_font_family'},
        )
        self.assertEqual(widget_context['widget']['attrs'].get('data-font-picker'), 'true')
        self.assertIn('popular-fonts', widget_context['widget']['attrs'].get('data-font-packs'))
        self.assertIn('modern-sans', widget_context['widget']['attrs'].get('data-designer-font-libraries'))
        self.assertEqual(widget_context['widget']['attrs'].get('data-font-favorites-key'), 'ownbasket-favorite-fonts')
        self.assertEqual(widget_context['widget']['attrs'].get('data-font-api-url'), reverse('fonts:active-fonts-api'))
        self.assertEqual(widget_context['widget']['attrs'].get('data-dropdown'), 'font-picker')

    def test_font_picker_entries_include_managed_fonts_and_legacy_fallbacks(self):
        ManagedFont.objects.create(
            name='Amsterdam Uploaded',
            css_name='Amsterdam Uploaded',
            category='script',
            source='upload',
            is_active=True,
            font_file=SimpleUploadedFile('amsterdam-1.woff2', b'fake-font', content_type='font/woff2'),
        )

        entries = get_active_font_entries(current_values=['Custom Legacy Font'])
        css_names = [entry['css_name'] for entry in entries]

        self.assertIn('Amsterdam Uploaded', css_names)
        self.assertIn('Inter', css_names)
        self.assertIn('Plus Jakarta Sans', css_names)
        self.assertIn('Custom Legacy Font', css_names)

    def test_google_fonts_url_uses_only_active_banner_font_families(self):
        BannerCarousel.objects.create(
            badge_text='TYPO',
            heading='Google Font Banner',
            description='Uses dynamic Google font loading.',
            button_text='Preview',
            button_url='https://example.com/preview',
            layout_template='layout_1',
            badge_font_family='Inter',
            heading_font_family='Playfair Display',
            description_font_family='DM Sans',
            button_font_family='Inter',
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('google-banner.jpg', b'fake-image-bytes', content_type='image/jpeg'),
        )

        google_fonts_url = ownbasket_google_fonts_url()

        self.assertIn('family=Inter', google_fonts_url)
        self.assertIn('family=Playfair+Display', google_fonts_url)
        self.assertIn('family=DM+Sans', google_fonts_url)
        self.assertNotIn('family=Varela+Round', google_fonts_url)

    def test_homepage_settings_form_uses_color_picker_widgets(self):
        form = HomepageSettingsAdminForm()

        self.assertIn('ve-color-source', form.fields['hero_background_color'].widget.attrs.get('class', ''))
        self.assertIn('ve-color-source', form.fields['promo_background_color'].widget.attrs.get('class', ''))

    def test_banner_admin_uses_visual_editor_change_form_template(self):
        admin_instance = BannerCarouselAdmin(BannerCarousel, AdminSite())

        self.assertEqual(admin_instance.change_form_template, 'admin/visual_editor_change_form.html')

    def test_banner_admin_add_page_renders_live_preview_panel(self):
        self.client.force_login(self.admin_user)

        response = self.client.get('/admin/banners/bannercarousel/add/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 've-live-preview')
        self.assertContains(response, 'ownbasket_visual_editor.js')
        self.assertContains(response, '<details open><summary>', html=False)
        self.assertContains(response, 'Typography')
        self.assertContains(response, 'Button Builder')
        self.assertContains(response, 'id_heading_font_family')
        self.assertContains(response, 'id_button_font_family')
        self.assertContains(response, 'data-font-preview="true"')
        self.assertContains(response, 'data-font-picker="true"')
        self.assertContains(response, 'data-font-recent-key="ownbasket-recent-fonts"')
        self.assertContains(response, 'data-font-favorites-key="ownbasket-favorite-fonts"')
        self.assertContains(response, 'data-designer-font-libraries=')
        self.assertContains(response, 'data-font-api-url="/fonts/api/"')
        self.assertContains(response, 'family=Inter')
        self.assertContains(response, 'family=Plus+Jakarta+Sans')

    def test_searchable_dropdown_assets_use_body_portal_rendering(self):
        js_asset = Path(settings.BASE_DIR) / 'static' / 'admin' / 'ownbasket_visual_editor.js'
        css_asset = Path(settings.BASE_DIR) / 'static' / 'admin' / 'ownbasket_visual_editor.css'

        js_content = js_asset.read_text(encoding='utf-8')
        css_content = css_asset.read_text(encoding='utf-8')

        self.assertIn('document.body.appendChild(dropdown);', js_content)
        self.assertIn('let activeSearchDropdown = null;', js_content)
        self.assertIn("document.addEventListener('pointerdown', function (event) {", js_content)
        self.assertIn("document.addEventListener('keydown', function (event) {", js_content)
        self.assertIn("activeSearchDropdown.close({ restoreFocus: false });", js_content)
        self.assertIn("event.key !== 'Escape'", js_content)
        self.assertIn("const fontPacks = isFontPicker ? parseJson(select.dataset.fontPacks || '[]', []) : [];", js_content)
        self.assertIn("const favoriteStorageKey = select.dataset.fontFavoritesKey || 'ownbasket-favorite-fonts';", js_content)
        self.assertIn('const recentStorageKey = select.dataset.fontRecentKey || \'ownbasket-recent-fonts\';', js_content)
        self.assertIn("const packSelect = createElement('select', 've-font-pack-select');", js_content)
        self.assertIn("const designerSelect = createElement('select', 've-font-pack-select');", js_content)
        self.assertIn("const designerLabel = createElement('label', 've-font-pack-label', 'Designer Font Library');", js_content)
        self.assertIn("const dropdownType = select.dataset.dropdown || 'native-select';", js_content)
        self.assertIn("const isFontPicker = dropdownType === 'font-picker' && select.dataset.fontPicker === 'true';", js_content)
        self.assertIn("function getNativeSelectEntries(nativeSelect) {", js_content)
        self.assertIn("const ALL_PACK_SLUG = 'all-fonts';", js_content)
        self.assertIn("const ALL_DESIGNER_LIBRARY_SLUG = 'all-designer-fonts';", js_content)
        self.assertIn("const loadedGoogleFontFamilies = new Set();", js_content)
        self.assertIn("const previewCard = createElement('div', 've-font-preview-card');", js_content)
        self.assertIn("const designerFontLibraries = isFontPicker ? parseJson(select.dataset.designerFontLibraries || '[]', []) : [];", js_content)
        self.assertIn("favoriteWrap.appendChild(favoriteHeading);", js_content)
        self.assertIn(
            "widget_attrs['data-font-api-url'] = reverse('fonts:active-fonts-api')",
            (Path(settings.BASE_DIR) / 'fonts' / 'widgets.py').read_text(encoding='utf-8'),
        )
        self.assertIn("widget_attrs['data-dropdown'] = 'font-picker'", (Path(settings.BASE_DIR) / 'fonts' / 'widgets.py').read_text(encoding='utf-8'))
        self.assertIn("attrs.setdefault('data-dropdown', 'native-select')", (Path(settings.BASE_DIR) / 'core' / 'admin_visual_editor.py').read_text(encoding='utf-8'))
        self.assertIn("widget_attrs['data-designer-font-libraries'] = json.dumps(self.designer_font_libraries)", (Path(settings.BASE_DIR) / 'fonts' / 'widgets.py').read_text(encoding='utf-8'))
        self.assertIn('position: fixed;', css_content)
        self.assertIn('z-index: 10000;', css_content)
        self.assertIn('.ve-search-dropdown[hidden] {', css_content)
        self.assertIn('display: none !important;', css_content)
        self.assertIn('.ve-search-controls {', css_content)
        self.assertIn('.ve-search-controls--font-picker {', css_content)
        self.assertIn('.ve-font-pack-select {', css_content)
        self.assertIn('.ve-font-preview-card {', css_content)
        self.assertIn('.ve-search-favorites {', css_content)
        self.assertIn('.ve-search-recent {', css_content)

    def test_banner_admin_change_page_handles_empty_background_image(self):
        self.client.force_login(self.admin_user)
        banner = BannerCarousel.objects.create(
            badge_text='Preview',
            heading='Preview Banner',
            description='Visual editor should not crash on empty background image.',
            button_text='Shop',
            button_url='https://example.com/shop',
            layout_template='layout_1',
            background_type='image',
            background_image=None,
            display_order=1,
            is_active=True,
            slide_duration=5000,
            image=SimpleUploadedFile('preview.jpg', b'preview-image', content_type='image/jpeg'),
        )

        response = self.client.get(f'/admin/banners/bannercarousel/{banner.pk}/change/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 've-live-preview')
        self.assertContains(response, '<details open><summary>', html=False)
