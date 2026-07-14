# Generated for Phase 9 review moderation.

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0013_productlistingsettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('title', models.CharField(blank=True, max_length=160)),
                ('body', models.TextField()),
                ('moderation_status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], db_index=True, default='pending', max_length=12)),
                ('moderation_notes', models.TextField(blank=True)),
                ('moderated_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('moderated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='moderated_product_reviews', to=settings.AUTH_USER_MODEL)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='products.product')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at', '-id'),
                'permissions': (('moderate_productreview', 'Can moderate product reviews'),),
                'constraints': [models.UniqueConstraint(fields=('product', 'user'), name='unique_product_review_per_customer')],
            },
        ),
    ]
