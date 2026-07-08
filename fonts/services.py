from django.db.models import Prefetch, Q
from django.urls import reverse

from .catalog import (
    DESIGNER_FONT_LIBRARIES,
    DESIGNER_LIBRARY_FONT_NAMES,
    PACK_FONT_NAMES,
    TYPOGRAPHY_PACKS,
    get_all_catalog_font_names,
    get_designer_library_names_for_font,
    get_designer_library_slugs_for_font,
    get_font_style_label,
    infer_font_category,
)
from .models import ManagedFont, ManagedFontPack, ManagedFontPackFont


def bootstrap_typography_catalog():
    seed_default_fonts()
    seed_default_font_packs()
    sync_system_google_fonts()
    assign_default_font_packs()


def seed_default_fonts():
    # Preserve previously seeded custom library entries as inactive upload-based records.
    legacy_defaults = [
        {'name': 'Brittany', 'css_name': 'Brittany', 'category': 'script'},
        {'name': 'Twister', 'css_name': 'Twister', 'category': 'display'},
        {'name': 'Mistrully', 'css_name': 'Mistrully', 'category': 'script'},
        {'name': 'Amsterdam 4', 'css_name': 'Amsterdam 4', 'category': 'script'},
        {'name': 'Sunday', 'css_name': 'Sunday', 'category': 'script'},
        {'name': 'Euphoria', 'css_name': 'Euphoria', 'category': 'script'},
        {'name': 'Kaushan', 'css_name': 'Kaushan', 'category': 'script'},
        {'name': 'Clicker', 'css_name': 'Clicker', 'category': 'script'},
        {'name': 'Playlist', 'css_name': 'Playlist', 'category': 'script'},
        {'name': 'Themysion', 'css_name': 'Themysion', 'category': 'script'},
        {'name': 'Bright Sunshine', 'css_name': 'Bright Sunshine', 'category': 'handwriting'},
        {'name': 'Moontime', 'css_name': 'Moontime', 'category': 'script'},
        {'name': 'Jimmy', 'css_name': 'Jimmy', 'category': 'handwriting'},
        {'name': 'Amsterdam 1', 'css_name': 'Amsterdam 1', 'category': 'script'},
        {'name': 'Tropika Script', 'css_name': 'Tropika Script', 'category': 'script'},
        {'name': 'Beth Ellen', 'css_name': 'Beth Ellen', 'category': 'handwriting'},
        {'name': 'Shadows Into Light', 'css_name': 'Shadows Into Light', 'category': 'handwriting'},
        {'name': 'Virtual', 'css_name': 'Virtual', 'category': 'display'},
        {'name': 'Bakerie', 'css_name': 'Bakerie', 'category': 'script'},
        {'name': 'Bright Sunshine Caps', 'css_name': 'Bright Sunshine Caps', 'category': 'display'},
        {'name': 'Aloja', 'css_name': 'Aloja', 'category': 'script'},
        {'name': 'Architects Daughter', 'css_name': 'Architects Daughter', 'category': 'handwriting'},
        {'name': 'Pony Club', 'css_name': 'Pony Club', 'category': 'script'},
        {'name': 'Trocchi', 'css_name': 'Trocchi', 'category': 'serif'},
        {'name': 'Purisa', 'css_name': 'Purisa', 'category': 'handwriting'},
        {'name': 'Finger Paint', 'css_name': 'Finger Paint', 'category': 'handwriting'},
        {'name': 'Sue Ellen', 'css_name': 'Sue Ellen', 'category': 'handwriting'},
        {'name': 'Porcelain', 'css_name': 'Porcelain', 'category': 'script'},
        {'name': 'Over the Rainbow', 'css_name': 'Over the Rainbow', 'category': 'handwriting'},
        {'name': 'Apricots', 'css_name': 'Apricots', 'category': 'handwriting'},
        {'name': 'Calistoga', 'css_name': 'Calistoga', 'category': 'serif'},
        {'name': 'Brusher', 'css_name': 'Brusher', 'category': 'script'},
        {'name': 'Charm', 'css_name': 'Charm', 'category': 'script'},
        {'name': 'Schoolbell', 'css_name': 'Schoolbell', 'category': 'handwriting'},
        {'name': 'Drukaatie Burti', 'css_name': 'Drukaatie Burti', 'category': 'display'},
        {'name': 'Amsterdam 3', 'css_name': 'Amsterdam 3', 'category': 'script'},
        {'name': 'Coming Soon', 'css_name': 'Coming Soon', 'category': 'handwriting'},
        {'name': 'Water Lilly', 'css_name': 'Water Lilly', 'category': 'script'},
        {'name': 'Daydream', 'css_name': 'Daydream', 'category': 'script'},
        {'name': 'Ojisey', 'css_name': 'Ojisey', 'category': 'display'},
        {'name': 'Homemade Apple', 'css_name': 'Homemade Apple', 'category': 'handwriting'},
        {'name': 'Liu Jian', 'css_name': 'Liu Jian', 'category': 'handwriting'},
        {'name': 'Lemon Tuesday', 'css_name': 'Lemon Tuesday', 'category': 'script'},
        {'name': 'Railey', 'css_name': 'Railey', 'category': 'script'},
        {'name': 'Give You Glory', 'css_name': 'Give You Glory', 'category': 'handwriting'},
        {'name': 'Kage', 'css_name': 'Kage', 'category': 'display'},
        {'name': 'More Sugar', 'css_name': 'More Sugar', 'category': 'script'},
        {'name': 'Livvic', 'css_name': 'Livvic', 'category': 'sans-serif'},
        {'name': 'Chewy', 'css_name': 'Chewy', 'category': 'display'},
        {'name': 'Amsterdam 2', 'css_name': 'Amsterdam 2', 'category': 'script'},
        {'name': 'Shadow', 'css_name': 'Shadow', 'category': 'display'},
    ]

    for font in legacy_defaults:
        ManagedFont.objects.get_or_create(
            name=font['name'],
            defaults={
                'css_name': font['css_name'],
                'category': font['category'],
                'source': 'upload',
                'is_active': False,
            },
        )


def sync_system_google_fonts():
    for index, font_name in enumerate(sorted(get_all_catalog_font_names())):
        category = infer_font_category(font_name)
        style_label = get_font_style_label(font_name, category)
        font, created = ManagedFont.objects.get_or_create(
            name=font_name,
            defaults={
                'css_name': font_name,
                'source': 'google',
                'google_family': font_name,
                'category': category,
                'style_label': style_label,
                'is_active': True,
                'sort_order': 100 + index,
            },
        )
        if created:
            continue
        if font.source == 'upload':
            continue
        font.css_name = font_name
        font.google_family = font_name
        font.category = category
        font.style_label = style_label
        font.is_active = True
        font.source = 'google'
        font.save(update_fields=[
            'css_name',
            'google_family',
            'category',
            'style_label',
            'is_active',
            'source',
            'updated_at',
        ])


def seed_default_font_packs():
    active_slugs = set()
    for pack in TYPOGRAPHY_PACKS:
        active_slugs.add(pack['slug'])
        ManagedFontPack.objects.update_or_create(
            slug=pack['slug'],
            defaults={
                'name': pack['name'],
                'group': pack['group'],
                'description': pack['description'],
                'sort_order': pack['sort_order'],
                'is_active': True,
            },
        )

    ManagedFontPack.objects.exclude(slug__in=active_slugs).filter(
        slug__in=[
            'premium-fonts', 'logo-fonts', 'branding-fonts', 'banner-fonts', 'popular-fonts',
            'trending-fonts', 'new-fonts', 'e-commerce', 'business', 'startup', 'corporate',
            'finance', 'real-estate', 'restaurant', 'healthcare', 'education',
            'social-media', 'youtube-thumbnail', 'flyer', 'business-card', 'sans-serif',
            'serif', 'script', 'handwritten', 'display', 'brush', 'calligraphy', 'luxury',
            'elegant', 'minimal', 'modern', 'rounded', 'decorative', 'monospace',
            'wedding', 'fashion', 'beauty', 'tech', 'gaming', 'kids', 'sports',
            'food', 'festival', 'travel', 'photography', 'vintage', 'retro',
        ]
    ).update(is_active=False)


def assign_default_font_packs():
    sync_system_google_fonts()
    slug_to_pack = {
        pack.slug: pack
        for pack in ManagedFontPack.objects.filter(is_active=True)
    }
    if not slug_to_pack:
        return

    existing_links = {
        (link.font_id, link.pack_id): link
        for link in ManagedFontPackFont.objects.select_related('pack')
    }

    for pack_slug, font_names in PACK_FONT_NAMES.items():
        pack = slug_to_pack.get(pack_slug)
        if pack is None:
            continue
        for index, font_name in enumerate(font_names):
            try:
                font = ManagedFont.objects.get(name=font_name)
            except ManagedFont.DoesNotExist:
                continue
            link = existing_links.get((font.pk, pack.pk))
            if link is None:
                ManagedFontPackFont.objects.create(
                    font=font,
                    pack=pack,
                    sort_order=index,
                )
            elif link.sort_order != index:
                ManagedFontPackFont.objects.filter(pk=link.pk).update(sort_order=index)


def get_font_pack_entries():
    return [
        {
            'id': pack.pk,
            'name': pack.name,
            'slug': pack.slug,
            'group': pack.group,
            'description': pack.description,
        }
        for pack in ManagedFontPack.objects.filter(is_active=True).order_by('sort_order', 'name', 'id')
    ]


def get_designer_font_library_entries():
    return [
        {
            'name': item['name'],
            'slug': item['slug'],
            'description': item['description'],
        }
        for item in sorted(DESIGNER_FONT_LIBRARIES, key=lambda item: (item['sort_order'], item['name']))
    ]


def _font_entry_from_model(font):
    pack_links = [link for link in font.pack_links.all() if link.pack.is_active]
    return {
        'id': font.pk,
        'name': font.name,
        'css_name': font.css_name,
        'category': font.category,
        'preview': font.preview_url,
        'font_url': font.font_url,
        'packs': [link.pack.slug for link in pack_links],
        'pack_names': [link.pack.name for link in pack_links],
        'style_label': font.style_label or get_font_style_label(font.name, font.category),
        'source': font.source,
        'google_family': font.google_family or font.css_name,
        'designer_libraries': get_designer_library_slugs_for_font(font.name),
        'designer_library_names': get_designer_library_names_for_font(font.name),
    }


def get_active_font_entries(current_values=None, pack_slug=None, designer_slug=None):
    current_values = [value for value in (current_values or []) if value]
    queryset = ManagedFont.objects.prefetch_related(
        Prefetch(
            'pack_links',
            queryset=ManagedFontPackFont.objects.select_related('pack').order_by('sort_order', 'pack__sort_order', 'pack__name'),
        )
    ).filter(is_active=True)

    if pack_slug and pack_slug != 'all-fonts':
        queryset = queryset.filter(
            Q(pack_links__pack__slug=pack_slug, pack_links__pack__is_active=True) |
            Q(css_name__in=current_values)
        )

    if designer_slug and designer_slug != 'all-designer-fonts':
        queryset = queryset.filter(
            Q(name__in=DESIGNER_LIBRARY_FONT_NAMES.get(designer_slug, [])) |
            Q(css_name__in=current_values)
        )

    entries = [
        _font_entry_from_model(font)
        for font in queryset.order_by('name', 'id').distinct()
    ]

    existing_css_names = {entry['css_name'] for entry in entries}
    for value in current_values:
        if value in existing_css_names:
            continue
        entries.append({
            'id': None,
            'name': value,
            'css_name': value,
            'category': 'sans-serif',
            'preview': '',
            'font_url': '',
            'packs': [],
            'pack_names': [],
            'style_label': 'Saved Custom Font',
            'source': 'legacy',
            'google_family': value,
        })

    return sorted(entries, key=lambda entry: (entry['name'].lower(), entry['css_name'].lower()))


def get_font_picker_choices(current_values=None):
    return [
        (entry['css_name'], entry['name'])
        for entry in get_active_font_entries(current_values=current_values)
    ]


def get_active_google_font_families(font_names=None):
    queryset = ManagedFont.objects.filter(is_active=True, source='google')
    if font_names:
        queryset = queryset.filter(css_name__in=font_names)
    return sorted({
        (font.google_family or font.css_name)
        for font in queryset
        if (font.google_family or font.css_name)
    })


def build_font_face_css():
    lines = []
    for font in ManagedFont.objects.filter(source='upload', is_active=True).exclude(font_file='').exclude(font_file__isnull=True).order_by('sort_order', 'name', 'id'):
        if not font.font_url or not font.font_format:
            continue
        lines.append('@font-face {')
        lines.append(f"  font-family: '{font.css_name}';")
        lines.append(f"  src: url('{reverse('fonts:font-file', args=[font.pk])}') format('{font.font_format}');")
        lines.append('  font-display: swap;')
        lines.append('  font-style: normal;')
        lines.append('  font-weight: 400;')
        lines.append('}')
        lines.append('')
    return '\n'.join(lines).strip()
