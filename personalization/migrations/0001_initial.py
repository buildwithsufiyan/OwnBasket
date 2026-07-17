import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0015_product_seller'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchSynonym',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('canonical_term', models.CharField(max_length=80, unique=True)),
                ('alternatives', models.JSONField(blank=True, default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ('canonical_term', 'id')},
        ),
        migrations.CreateModel(
            name='BehaviorEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_hash', models.CharField(blank=True, db_index=True, max_length=64)),
                ('event_type', models.CharField(choices=[('product_view', 'Product view'), ('category_view', 'Category view'), ('brand_view', 'Brand view'), ('search', 'Search'), ('wishlist_add', 'Wishlist add'), ('wishlist_remove', 'Wishlist remove'), ('cart_add', 'Cart add/update'), ('cart_remove', 'Cart remove')], db_index=True, max_length=24)),
                ('search_term', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('brand', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='behavior_events', to='products.brand')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='behavior_events', to='products.category')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='behavior_events', to='products.product')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='behavior_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at', '-id'),
                'indexes': [
                    models.Index(fields=['event_type', 'created_at'], name='behavior_type_created_idx'),
                    models.Index(fields=['user', 'event_type', 'created_at'], name='behavior_user_type_idx'),
                    models.Index(fields=['product', 'event_type', 'created_at'], name='behavior_product_type_idx'),
                ],
            },
        ),
    ]
