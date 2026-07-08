from django.db import migrations


DEFAULT_FONT_LIBRARY = [
    ('Brittany', 'Brittany', 'script'),
    ('Twister', 'Twister', 'display'),
    ('Mistrully', 'Mistrully', 'script'),
    ('Amsterdam 4', 'Amsterdam 4', 'script'),
    ('Sunday', 'Sunday', 'script'),
    ('Euphoria', 'Euphoria', 'script'),
    ('Kaushan', 'Kaushan', 'script'),
    ('Clicker', 'Clicker', 'script'),
    ('Playlist', 'Playlist', 'script'),
    ('Themysion', 'Themysion', 'script'),
    ('Bright Sunshine', 'Bright Sunshine', 'handwriting'),
    ('Moontime', 'Moontime', 'script'),
    ('Jimmy', 'Jimmy', 'handwriting'),
    ('Amsterdam 1', 'Amsterdam 1', 'script'),
    ('Tropika Script', 'Tropika Script', 'script'),
    ('Beth Ellen', 'Beth Ellen', 'handwriting'),
    ('Shadows Into Light', 'Shadows Into Light', 'handwriting'),
    ('Virtual', 'Virtual', 'display'),
    ('Bakerie', 'Bakerie', 'script'),
    ('Bright Sunshine Caps', 'Bright Sunshine Caps', 'display'),
    ('Aloja', 'Aloja', 'script'),
    ('Architects Daughter', 'Architects Daughter', 'handwriting'),
    ('Pony Club', 'Pony Club', 'script'),
    ('Trocchi', 'Trocchi', 'serif'),
    ('Purisa', 'Purisa', 'handwriting'),
    ('Finger Paint', 'Finger Paint', 'handwriting'),
    ('Sue Ellen', 'Sue Ellen', 'handwriting'),
    ('Porcelain', 'Porcelain', 'script'),
    ('Over the Rainbow', 'Over the Rainbow', 'handwriting'),
    ('Apricots', 'Apricots', 'handwriting'),
    ('Calistoga', 'Calistoga', 'serif'),
    ('Brusher', 'Brusher', 'script'),
    ('Charm', 'Charm', 'script'),
    ('Schoolbell', 'Schoolbell', 'handwriting'),
    ('Drukaatie Burti', 'Drukaatie Burti', 'display'),
    ('Amsterdam 3', 'Amsterdam 3', 'script'),
    ('Coming Soon', 'Coming Soon', 'handwriting'),
    ('Water Lilly', 'Water Lilly', 'script'),
    ('Daydream', 'Daydream', 'script'),
    ('Ojisey', 'Ojisey', 'display'),
    ('Homemade Apple', 'Homemade Apple', 'handwriting'),
    ('Liu Jian', 'Liu Jian', 'handwriting'),
    ('Lemon Tuesday', 'Lemon Tuesday', 'script'),
    ('Railey', 'Railey', 'script'),
    ('Give You Glory', 'Give You Glory', 'handwriting'),
    ('Kage', 'Kage', 'display'),
    ('More Sugar', 'More Sugar', 'script'),
    ('Livvic', 'Livvic', 'sans-serif'),
    ('Chewy', 'Chewy', 'display'),
    ('Amsterdam 2', 'Amsterdam 2', 'script'),
    ('Shadow', 'Shadow', 'display'),
]


def seed_default_fonts(apps, schema_editor):
    ManagedFont = apps.get_model('fonts', 'ManagedFont')
    for name, css_name, category in DEFAULT_FONT_LIBRARY:
        ManagedFont.objects.get_or_create(
            name=name,
            defaults={
                'css_name': css_name,
                'category': category,
                'is_active': False,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('fonts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_default_fonts, migrations.RunPython.noop),
    ]
