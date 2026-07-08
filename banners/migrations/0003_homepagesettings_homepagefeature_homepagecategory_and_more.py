from urllib.parse import parse_qs, urlparse

from django.db import migrations, models


def forwards_copy_homepage_data(apps, schema_editor):
    HomepageSettings = apps.get_model('banners', 'HomepageSettings')
    HomepageFeature = apps.get_model('banners', 'HomepageFeature')
    HomepageCategory = apps.get_model('banners', 'HomepageCategory')
    HeroBanner = apps.get_model('banners', 'HeroBanner')
    HomeFeature = apps.get_model('banners', 'HomeFeature')
    HomeCategorySection = apps.get_model('banners', 'HomeCategorySection')
    PromoBanner = apps.get_model('banners', 'PromoBanner')
    Category = apps.get_model('products', 'Category')

    hero_banner = (
        HeroBanner.objects.filter(is_active=True).order_by('order', 'id').first()
        or HeroBanner.objects.order_by('order', 'id').first()
    )
    promo_banner = (
        PromoBanner.objects.filter(is_active=True).order_by('id').first()
        or PromoBanner.objects.order_by('id').first()
    )

    HomepageSettings.objects.create(
        hero_badge_text=getattr(hero_banner, 'badge_text', '') or 'UP TO 50% OFF',
        hero_heading=getattr(hero_banner, 'title', '') or 'UPCOMING SOON',
        hero_subheading=getattr(hero_banner, 'subtitle', '') or 'Your One-Stop Online Shopping Destination',
        hero_button_text=getattr(hero_banner, 'button_text', '') or 'Stay Tuned!',
        hero_button_link=getattr(hero_banner, 'button_link', '') or '/home/',
        hero_image=getattr(hero_banner, 'image', None),
        hero_background_color=getattr(hero_banner, 'bg_color', '') or '#f3f4f6',
        promo_small_text=getattr(promo_banner, 'main_title', '') or 'THIS WEBSITE IS',
        promo_main_heading=getattr(promo_banner, 'highlight_text', '') or 'UPCOMING SOON',
        promo_tagline=getattr(promo_banner, 'sub_text', '') or 'STAY TUNED!',
        promo_developer_name=getattr(promo_banner, 'developer_name', ''),
        promo_email=getattr(promo_banner, 'email', ''),
        promo_contact_number=getattr(promo_banner, 'phone', ''),
        promo_image=getattr(promo_banner, 'side_image', None),
        promo_background_color=getattr(promo_banner, 'bg_color', '') or '#ffb800',
    )

    for feature in HomeFeature.objects.all().order_by('order', 'id'):
        HomepageFeature.objects.create(
            icon=feature.icon,
            title=feature.title,
            description=feature.description,
            display_order=feature.order,
            is_active=feature.is_active,
        )

    for home_category in HomeCategorySection.objects.all().order_by('order', 'id'):
        linked_category = None
        link_url = getattr(home_category, 'link_url', '') or ''
        if link_url:
            parsed = urlparse(link_url)
            category_slug = parse_qs(parsed.query).get('category', [None])[0]
            if category_slug:
                linked_category = Category.objects.filter(slug=category_slug).first()

        HomepageCategory.objects.create(
            name=home_category.name,
            image=home_category.image,
            linked_category=linked_category,
            display_order=home_category.order,
            is_active=home_category.is_active,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_remove_productspecification_rating_and_more'),
        ('banners', '0002_herobanner_homebrand_homecategorysection_homefeature_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='HomepageSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hero_badge_text', models.CharField(blank=True, default='UP TO 50% OFF', max_length=120, verbose_name='Small Badge Text')),
                ('hero_heading', models.CharField(default='UPCOMING SOON', max_length=200, verbose_name='Main Heading')),
                ('hero_subheading', models.CharField(blank=True, default='Your One-Stop Online Shopping Destination', max_length=300, verbose_name='Sub Heading')),
                ('hero_button_text', models.CharField(default='Stay Tuned!', max_length=80, verbose_name='Button Text')),
                ('hero_button_link', models.CharField(blank=True, default='/home/', max_length=255, verbose_name='Button Link')),
                ('hero_image', models.ImageField(blank=True, null=True, upload_to='homepage/hero/', verbose_name='Hero Image / Icon Upload')),
                ('hero_background_color', models.CharField(default='#f3f4f6', max_length=20, verbose_name='Hero Background Color')),
                ('promo_small_text', models.CharField(blank=True, default='THIS WEBSITE IS', max_length=120, verbose_name='Promotional Small Text')),
                ('promo_main_heading', models.CharField(default='UPCOMING SOON', max_length=200, verbose_name='Promotional Main Heading')),
                ('promo_tagline', models.CharField(blank=True, default='STAY TUNED!', max_length=200, verbose_name='Promotional Tagline')),
                ('promo_developer_name', models.CharField(blank=True, max_length=150, verbose_name='Developer Name')),
                ('promo_email', models.EmailField(blank=True, max_length=254, verbose_name='Email')),
                ('promo_contact_number', models.CharField(blank=True, max_length=20, verbose_name='Contact Number')),
                ('promo_image', models.ImageField(blank=True, null=True, upload_to='homepage/promo/', verbose_name='Right Side Image')),
                ('promo_background_color', models.CharField(default='#ffb800', max_length=20, verbose_name='Promotional Banner Background Color')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Homepage Settings',
                'verbose_name_plural': 'Homepage Settings',
            },
        ),
        migrations.CreateModel(
            name='HomepageFeature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('icon', models.CharField(choices=[('bi-truck', 'Truck'), ('bi-shield-check', 'Shield Check'), ('bi-arrow-repeat', 'Arrow Repeat'), ('bi-headset', 'Headset'), ('bi-credit-card', 'Credit Card'), ('bi-gift', 'Gift'), ('bi-box-seam', 'Box'), ('bi-star', 'Star'), ('bi-patch-check', 'Patch Check')], default='bi-truck', max_length=50, verbose_name='Icon')),
                ('title', models.CharField(max_length=100, verbose_name='Title')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='Description')),
                ('display_order', models.PositiveSmallIntegerField(default=0, verbose_name='Display Order')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
            ],
            options={
                'verbose_name': 'Homepage Feature',
                'verbose_name_plural': 'Homepage Features',
                'ordering': ['display_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='HomepageCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Category Name')),
                ('image', models.ImageField(blank=True, null=True, upload_to='homepage/categories/', verbose_name='Icon / Image')),
                ('display_order', models.PositiveSmallIntegerField(default=0, verbose_name='Display Order')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('linked_category', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='homepage_categories', to='products.category', verbose_name='Linked Product Category')),
            ],
            options={
                'verbose_name': 'Homepage Category',
                'verbose_name_plural': 'Homepage Categories',
                'ordering': ['display_order', 'id'],
            },
        ),
        migrations.RunPython(forwards_copy_homepage_data, migrations.RunPython.noop),
        migrations.DeleteModel(
            name='HomeBrand',
        ),
        migrations.DeleteModel(
            name='HomeCategorySection',
        ),
        migrations.DeleteModel(
            name='HomeFeature',
        ),
        migrations.DeleteModel(
            name='HeroBanner',
        ),
        migrations.DeleteModel(
            name='PromoBanner',
        ),
        migrations.DeleteModel(
            name='Banner',
        ),
        migrations.DeleteModel(
            name='Slider',
        ),
    ]
