from collections import defaultdict

from django.db import migrations


DEFAULT_FONT_PACKS = [
    ('Popular Fonts', 'popular-fonts', 'default', 'Most-used starter fonts for ecommerce creatives.', 0),
    ('Trending Fonts', 'trending-fonts', 'default', 'Fresh fonts that work well in current visual trends.', 1),
    ('New Fonts', 'new-fonts', 'default', 'Recently added fonts for discovery.', 2),
    ('Premium Fonts', 'premium-fonts', 'default', 'Luxury-looking fonts for premium campaigns.', 3),
    ('E-commerce', 'e-commerce', 'business', 'Fonts suitable for product banners and offers.', 10),
    ('Startup', 'startup', 'business', 'Clean and modern startup-focused fonts.', 11),
    ('Corporate', 'corporate', 'business', 'Professional fonts for corporate communication.', 12),
    ('Finance', 'finance', 'business', 'Trustworthy fonts for finance brands.', 13),
    ('Real Estate', 'real-estate', 'business', 'Balanced fonts for property marketing.', 14),
    ('Restaurant', 'restaurant', 'business', 'Fonts that work well for food and menu visuals.', 15),
    ('Healthcare', 'healthcare', 'business', 'Clear and reassuring healthcare fonts.', 16),
    ('Education', 'education', 'business', 'Friendly fonts for education creatives.', 17),
    ('Logo Fonts', 'logo-fonts', 'design', 'Fonts suited for logo concepts.', 20),
    ('Branding Fonts', 'branding-fonts', 'design', 'Fonts for brand identity systems.', 21),
    ('Poster Fonts', 'poster-fonts', 'design', 'Bold fonts for posters and ads.', 22),
    ('Banner Fonts', 'banner-fonts', 'design', 'Fonts optimized for hero banners.', 23),
    ('Social Media', 'social-media', 'design', 'Fonts tuned for social creatives.', 24),
    ('YouTube Thumbnail', 'youtube-thumbnail', 'design', 'Attention-grabbing fonts for thumbnails.', 25),
    ('Flyer', 'flyer', 'design', 'Fonts for promotional flyer layouts.', 26),
    ('Business Card', 'business-card', 'design', 'Refined fonts for business stationery.', 27),
    ('Sans Serif', 'sans-serif', 'style', 'Clean sans serif font collection.', 30),
    ('Serif', 'serif', 'style', 'Classic serif font collection.', 31),
    ('Script', 'script', 'style', 'Flowing script font collection.', 32),
    ('Handwritten', 'handwritten', 'style', 'Informal handwritten font collection.', 33),
    ('Display', 'display', 'style', 'High-impact display fonts.', 34),
    ('Brush', 'brush', 'style', 'Brush-style expressive fonts.', 35),
    ('Calligraphy', 'calligraphy', 'style', 'Elegant calligraphy-inspired fonts.', 36),
    ('Luxury', 'luxury', 'style', 'Premium and luxury-looking fonts.', 37),
    ('Elegant', 'elegant', 'style', 'Elegant fonts for polished visuals.', 38),
    ('Minimal', 'minimal', 'style', 'Minimal and clean fonts.', 39),
    ('Modern', 'modern', 'style', 'Modern fonts for current design systems.', 40),
    ('Rounded', 'rounded', 'style', 'Rounded fonts with friendly character.', 41),
    ('Decorative', 'decorative', 'style', 'Decorative fonts for standout creatives.', 42),
    ('Monospace', 'monospace', 'style', 'Monospace font collection.', 43),
    ('Wedding', 'wedding', 'special', 'Romantic fonts for wedding themes.', 50),
    ('Fashion', 'fashion', 'special', 'Refined fonts for fashion campaigns.', 51),
    ('Beauty', 'beauty', 'special', 'Elegant fonts for beauty brands.', 52),
    ('Tech', 'tech', 'special', 'Modern fonts for tech visuals.', 53),
    ('Gaming', 'gaming', 'special', 'Bold fonts for gaming creatives.', 54),
    ('Kids', 'kids', 'special', 'Friendly fonts for kids-focused graphics.', 55),
    ('Sports', 'sports', 'special', 'Dynamic fonts for sports branding.', 56),
    ('Food', 'food', 'special', 'Fonts suited to food promotions.', 57),
    ('Festival', 'festival', 'special', 'Celebratory fonts for festive campaigns.', 58),
    ('Travel', 'travel', 'special', 'Versatile fonts for travel graphics.', 59),
    ('Photography', 'photography', 'special', 'Fonts for photography portfolios and promos.', 60),
    ('Vintage', 'vintage', 'special', 'Vintage-inspired fonts.', 61),
    ('Retro', 'retro', 'special', 'Retro and nostalgic font collection.', 62),
]


def seed_default_font_packs(apps, schema_editor):
    ManagedFont = apps.get_model('fonts', 'ManagedFont')
    ManagedFontPack = apps.get_model('fonts', 'ManagedFontPack')
    ManagedFontPackFont = apps.get_model('fonts', 'ManagedFontPackFont')

    for name, slug, group, description, sort_order in DEFAULT_FONT_PACKS:
        ManagedFontPack.objects.get_or_create(
            slug=slug,
            defaults={
                'name': name,
                'group': group,
                'description': description,
                'sort_order': sort_order,
                'is_active': True,
            },
        )

    slug_to_pack = {pack.slug: pack for pack in ManagedFontPack.objects.all()}
    font_links = defaultdict(set)

    for font in ManagedFont.objects.all():
        font_name = font.name.lower()
        category_slug = 'handwritten' if font.category == 'handwriting' else font.category
        if category_slug in slug_to_pack:
            font_links[font.pk].add(category_slug)

        if font.category in {'script', 'handwriting'}:
            font_links[font.pk].update({'popular-fonts', 'branding-fonts', 'banner-fonts'})
        if font.category == 'sans-serif':
            font_links[font.pk].update({'popular-fonts', 'e-commerce', 'startup', 'modern', 'minimal'})
        if font.category == 'serif':
            font_links[font.pk].update({'premium-fonts', 'corporate', 'elegant'})
        if font.category == 'display':
            font_links[font.pk].update({'trending-fonts', 'poster-fonts', 'youtube-thumbnail', 'decorative'})

        if any(keyword in font_name for keyword in ('amsterdam', 'brittany', 'aloja', 'euphoria', 'themysion')):
            font_links[font.pk].update({'wedding', 'luxury', 'calligraphy', 'fashion', 'beauty'})
        if any(keyword in font_name for keyword in ('chewy', 'finger paint', 'schoolbell')):
            font_links[font.pk].update({'kids', 'festival'})
        if any(keyword in font_name for keyword in ('livvic', 'shadow', 'virtual', 'kage')):
            font_links[font.pk].update({'tech', 'gaming', 'modern'})
        if any(keyword in font_name for keyword in ('calistoga', 'trocchi', 'porcelain')):
            font_links[font.pk].update({'vintage', 'retro', 'logo-fonts'})

    existing_links = {
        (link.font_id, link.pack_id)
        for link in ManagedFontPackFont.objects.all()
    }

    created_links = []
    for font in ManagedFont.objects.all():
        for index, slug in enumerate(sorted(font_links.get(font.pk, set()))):
            pack = slug_to_pack.get(slug)
            if not pack or (font.pk, pack.pk) in existing_links:
                continue
            created_links.append(
                ManagedFontPackFont(font_id=font.pk, pack_id=pack.pk, sort_order=index)
            )

    if created_links:
        ManagedFontPackFont.objects.bulk_create(created_links)


class Migration(migrations.Migration):
    dependencies = [
        ('fonts', '0003_managedfontpack_managedfontpackfont_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_default_font_packs, migrations.RunPython.noop),
    ]
