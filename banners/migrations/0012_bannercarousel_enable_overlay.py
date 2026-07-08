from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banners', '0011_bannercarousel_animation_delay_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bannercarousel',
            name='enable_overlay',
            field=models.BooleanField(default=True, verbose_name='Enable Overlay'),
        ),
    ]
