from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg
from django.urls import reverse
from django.utils.text import slugify
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    category_image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    @property
    def target_url(self):
        return reverse('products:category_detail', args=[self.slug])


class SubCategory(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='subcategories',
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    image = models.ImageField(
        upload_to='subcategories/',
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('sort_order', 'name', 'id')
        unique_together = ('category', 'slug')

    def __str__(self):
        return f"{self.category.name} - {self.name}"

    @property
    def target_url(self):
        return f"{reverse('products:category_detail', args=[self.category.slug])}?subcategory={self.slug}"


class Brand(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(
        upload_to='brands/',
        blank=True,
        null=True
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def target_url(self):
        return reverse('products:brand_detail', args=[self.pk])


class BrandHeroBanner(models.Model):
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name='hero_banners',
    )
    banner_title = models.CharField(max_length=150, blank=True, null=True)
    banner_subtitle = models.CharField(max_length=255, blank=True, null=True)
    button_text = models.CharField(max_length=50, blank=True, null=True)
    button_url = models.CharField(max_length=255, blank=True, null=True)
    cover_image = models.ImageField(upload_to='brands/hero_banners/')
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('display_order', 'id')
        verbose_name = 'Brand Hero Banner'
        verbose_name_plural = 'Brand Hero Banners'

    def __str__(self):
        return f"{self.brand.name} - {(self.banner_title or 'Hero Banner')}"

    @property
    def has_title(self):
        return bool((self.banner_title or '').strip())

    @property
    def has_subtitle(self):
        return bool((self.banner_subtitle or '').strip())

    @property
    def has_button(self):
        return bool((self.button_text or '').strip())

    @property
    def has_content(self):
        return self.has_title or self.has_subtitle or self.has_button

    @property
    def resolved_button_text(self):
        return (self.button_text or '').strip()

    @property
    def resolved_button_url(self):
        return (self.button_url or '').strip() or '#'


class Warehouse(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30, unique=True)
    city = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name', 'id')

    def __str__(self):
        return f"{self.name} ({self.code})"


class DiscountType(models.TextChoices):
    PERCENTAGE = 'percentage', 'Percentage'
    FIXED = 'fixed', 'Fixed Amount'


class ActivationWindowMixin(models.Model):
    is_active = models.BooleanField(default=True)
    start_at = models.DateTimeField(blank=True, null=True)
    end_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def is_available(self, at_time=None):
        at_time = at_time or timezone.now()
        if not self.is_active:
            return False
        if self.start_at and self.start_at > at_time:
            return False
        if self.end_at and self.end_at < at_time:
            return False
        return True

    @property
    def is_currently_active(self):
        return self.is_available()

    def clean(self):
        super().clean()
        if self.start_at and self.end_at and self.start_at > self.end_at:
            raise ValidationError("Start date must be earlier than end date.")


class ValueDiscountMixin(models.Model):
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )
    value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    badge_text = models.CharField(max_length=80, blank=True)
    priority = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.value <= 0:
            raise ValidationError("Discount value must be greater than zero.")
        if self.discount_type == DiscountType.PERCENTAGE and self.value > 100:
            raise ValidationError("Percentage discount cannot exceed 100.")
        if self.max_discount_amount is not None and self.max_discount_amount <= 0:
            raise ValidationError("Max discount amount must be greater than zero.")


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE
    )

    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='products',
    )

    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE
    )

    name = models.CharField(max_length=255)

    sku = models.CharField(
        max_length=40,
        unique=True,
        blank=True,
        null=True,
    )

    slug = models.SlugField(
        unique=True,
        blank=True,
    )

    barcode = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        unique=True,
    )

    short_description = models.CharField(
        max_length=300,
        blank=True
    )

    description = models.TextField()

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )

    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )

    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )

    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False,
    )

    offer_start_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    offer_end_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    profit_margin = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False,
    )

    old_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )

    stock = models.PositiveIntegerField(
        default=0
    )

    image = models.ImageField(
        upload_to='products/'
    )

    video = models.FileField(
        upload_to='products/videos/',
        blank=True,
        null=True,
    )

    warranty = models.CharField(
        max_length=255,
        blank=True,
    )

    return_policy = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        default=4.5
    )

    reviews_count = models.PositiveIntegerField(
        default=0
    )

    delivery_text = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        default="FREE delivery Saturday, 28 June."
    )

    featured_product = models.BooleanField(default=False)
    recommended_product = models.BooleanField(default=False)
    flash_sale_product = models.BooleanField(default=False)
    deal_of_the_day = models.BooleanField(default=False)
    premium_choice = models.BooleanField(default=False)
    verified_product = models.BooleanField(default=False)
    free_delivery = models.BooleanField(default=False)
    cash_on_delivery = models.BooleanField(default=False)

    low_stock_alert = models.PositiveIntegerField(default=5)
    out_of_stock = models.BooleanField(default=False, editable=False)
    allow_backorder = models.BooleanField(default=False)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='products',
    )
    weight = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    length_cm = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    width_cm = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    height_cm = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)

    total_sold = models.PositiveIntegerField(default=0)
    total_views = models.PositiveIntegerField(default=0)
    wishlist_count = models.PositiveIntegerField(default=0)
    last_viewed_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:product_detail', args=[self.slug])

    def clean(self):
        super().clean()
        if self.subcategory_id and self.subcategory.category_id != self.category_id:
            raise ValidationError("Selected sub category must belong to the chosen category.")
        if self.offer_start_at and self.offer_end_at and self.offer_start_at > self.offer_end_at:
            raise ValidationError("Offer start date must be earlier than offer end date.")
        if self.cost_price < 0:
            raise ValidationError("Cost price cannot be negative.")
        if self.tax_percentage < 0:
            raise ValidationError("Tax percentage cannot be negative.")
        if self.discount_price is not None and self.discount_price < 0:
            raise ValidationError("Discount price cannot be negative.")
        if self.mrp is not None and self.mrp < 0:
            raise ValidationError("MRP cannot be negative.")
        if self.selling_price is not None and self.selling_price < 0:
            raise ValidationError("Selling price cannot be negative.")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        if not self.sku:
            self.sku = self._generate_unique_sku()

        if self.selling_price is None:
            self.selling_price = self.price
        self.price = self.selling_price or self.price

        if self.mrp is None and self.old_price:
            self.mrp = self.old_price
        if self.old_price is None and self.mrp:
            self.old_price = self.mrp

        self.out_of_stock = self.stock <= 0
        self.discount_percentage = self.calculate_discount_percentage()
        self.profit_margin = self.calculate_profit_margin()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        base_slug = slugify(self.name)[:45] or f"product-{uuid4().hex[:8]}"
        slug_candidate = base_slug
        counter = 1
        while Product.objects.exclude(pk=self.pk).filter(slug=slug_candidate).exists():
            slug_candidate = f"{base_slug[:40]}-{counter}"
            counter += 1
        return slug_candidate

    def _generate_unique_sku(self):
        category_code = (self.category.name[:3] if self.category_id else 'PRD').upper().replace(' ', '')
        brand_code = (self.brand.name[:3] if self.brand_id else 'GEN').upper().replace(' ', '')
        while True:
            candidate = f"{category_code}-{brand_code}-{uuid4().hex[:6].upper()}"
            if not Product.objects.exclude(pk=self.pk).filter(sku=candidate).exists():
                return candidate

    def has_active_offer(self, at_time=None):
        at_time = at_time or timezone.now()
        if not self.discount_price:
            return False
        if self.offer_start_at and self.offer_start_at > at_time:
            return False
        if self.offer_end_at and self.offer_end_at < at_time:
            return False
        return True

    def calculate_discount_percentage(self):
        compare_price = self.mrp or self.old_price or self.selling_price or self.price or Decimal('0.00')
        active_price = self.discount_price if self.discount_price and self.has_active_offer() else self.selling_price or self.price
        if not compare_price or not active_price or compare_price <= active_price:
            return Decimal('0.00')
        return ((compare_price - active_price) / compare_price * Decimal('100')).quantize(Decimal('0.01'))

    def calculate_profit_margin(self):
        sell_price = self.selling_price or self.price or Decimal('0.00')
        if not sell_price or sell_price <= 0:
            return Decimal('0.00')
        return ((sell_price - self.cost_price) / sell_price * Decimal('100')).quantize(Decimal('0.01'))

    @property
    def price_with_tax(self):
        current_price = self.discount_price if self.has_active_offer() else self.selling_price or self.price
        if not current_price:
            return Decimal('0.00')
        return (current_price * (Decimal('1.00') + (self.tax_percentage / Decimal('100')))).quantize(Decimal('0.01'))

    @property
    def is_best_seller_auto(self):
        return False

    @property
    def is_trending_auto(self):
        return False

    @property
    def is_new_arrival_auto(self):
        return False

    @property
    def is_limited_stock(self):
        return self.stock > 0 and self.stock <= self.low_stock_alert

    @property
    def active_badges(self):
        badges = []
        if self.featured_product:
            badges.append('Featured')
        if self.flash_sale_product:
            badges.append('Flash Sale')
        if self.recommended_product:
            badges.append('Recommended')
        if self.premium_choice:
            badges.append('Premium Choice')
        if self.deal_of_the_day:
            badges.append('Deal of the Day')
        if self.is_limited_stock:
            badges.append('Limited Stock')
        if self.free_delivery:
            badges.append('Free Delivery')
        if self.cash_on_delivery:
            badges.append('Cash on Delivery')
        if self.verified_product:
            badges.append('Verified Product')
        return badges

    def refresh_review_summary(self):
        """Keep storefront rating fields in sync with approved customer reviews."""
        summary = self.reviews.filter(
            moderation_status=ProductReview.ModerationStatus.APPROVED
        ).aggregate(average=Avg('rating'), total=models.Count('id'))
        self.rating = Decimal(str(summary['average'] or 0)).quantize(Decimal('0.1'))
        self.reviews_count = summary['total'] or 0
        self.save(update_fields=('rating', 'reviews_count'))


class ProductListingSettings(models.Model):
    """Singleton controls for the public shop listing page."""
    products_per_page = models.PositiveSmallIntegerField(default=24)
    default_sort = models.CharField(max_length=20, default="default")
    default_view = models.CharField(
        max_length=10, choices=(("grid", "Grid"), ("list", "List")), default="grid"
    )
    enable_filters = models.BooleanField(default=True)
    enable_view_toggle = models.BooleanField(default=True)
    enable_sidebar = models.BooleanField(default=True)
    enable_sticky_filters = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Product listing settings"
        verbose_name_plural = "Product listing settings"

    def clean(self):
        super().clean()
        if not 8 <= self.products_per_page <= 96:
            raise ValidationError("Products per page must be between 8 and 96.")
        if ProductListingSettings.objects.exclude(pk=self.pk).exists():
            raise ValidationError("Only one product listing settings record is allowed.")

    @classmethod
    def get_solo(cls):
        return cls.objects.order_by("pk").first() or cls()


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )

    variant_name = models.CharField(
        max_length=100
    )

    variant_value = models.CharField(
        max_length=100
    )

    def __str__(self):
        return f"{self.product.name} - {self.variant_name}: {self.variant_value}"


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='gallery'
    )

    image = models.ImageField(
        upload_to='products/gallery/'
    )

    def __str__(self):
        return self.product.name


class ProductFeature(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='features'
    )

    feature = models.CharField(
        max_length=255
    )

    def __str__(self):
        return self.feature


class ProductSpecification(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='specifications'
    )

    name = models.CharField(
        max_length=100
    )

    value = models.CharField(
        max_length=255
    )

    def __str__(self):
        return f"{self.name}: {self.value}"


class ProductReview(models.Model):
    class ModerationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='product_reviews',
    )
    rating = models.PositiveSmallIntegerField(
        validators=(MinValueValidator(1), MaxValueValidator(5)),
    )
    title = models.CharField(max_length=160, blank=True)
    body = models.TextField()
    moderation_status = models.CharField(
        max_length=12,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
        db_index=True,
    )
    moderation_notes = models.TextField(blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='moderated_product_reviews',
    )
    moderated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        constraints = (
            models.UniqueConstraint(
                fields=('product', 'user'),
                name='unique_product_review_per_customer',
            ),
        )
        permissions = (
            ('moderate_productreview', 'Can moderate product reviews'),
        )

    def __str__(self):
        return f"{self.product} - {self.user} ({self.rating}/5)"

    def save(self, *args, **kwargs):
        previous_product_id = None
        if self.pk:
            previous_product_id = type(self).objects.filter(pk=self.pk).values_list(
                'product_id', flat=True
            ).first()
        super().save(*args, **kwargs)
        self.product.refresh_review_summary()
        if previous_product_id and previous_product_id != self.product_id:
            Product.objects.get(pk=previous_product_id).refresh_review_summary()

    def delete(self, *args, **kwargs):
        product = self.product
        result = super().delete(*args, **kwargs)
        product.refresh_review_summary()
        return result


class ProductDiscount(ActivationWindowMixin, ValueDiscountMixin):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='discount_rules',
    )
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ('-priority', 'name', 'id')

    def __str__(self):
        return f"{self.name} - {self.product.name}"


class CategoryDiscount(ActivationWindowMixin, ValueDiscountMixin):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='discount_rules',
    )
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ('-priority', 'name', 'id')

    def __str__(self):
        return f"{self.name} - {self.category.name}"


class FlashSale(ActivationWindowMixin, ValueDiscountMixin):
    name = models.CharField(max_length=120)
    products = models.ManyToManyField(
        Product,
        blank=True,
        related_name='flash_sale_rules',
    )
    categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name='flash_sale_rules',
    )

    class Meta:
        ordering = ('start_at', 'end_at', 'name', 'id')

    def clean(self):
        super().clean()
        if not self.end_at:
            raise ValidationError("Flash sale end date is required.")

    def __str__(self):
        return self.name


class Coupon(ActivationWindowMixin, ValueDiscountMixin):
    code = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=120)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='coupons',
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='coupons',
    )
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    usage_limit = models.PositiveIntegerField(blank=True, null=True)
    usage_per_user = models.PositiveIntegerField(blank=True, null=True)
    free_shipping = models.BooleanField(default=False)
    first_order_only = models.BooleanField(default=False)

    class Meta:
        ordering = ('code',)

    def clean(self):
        super().clean()
        if self.min_order_amount < 0:
            raise ValidationError("Minimum order amount cannot be negative.")
        if self.usage_limit is not None and self.usage_limit <= 0:
            raise ValidationError("Usage limit must be greater than zero.")
        if self.usage_per_user is not None and self.usage_per_user <= 0:
            raise ValidationError("Usage per user must be greater than zero.")

    def save(self, *args, **kwargs):
        self.code = (self.code or '').upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class FreeShippingOffer(ActivationWindowMixin):
    name = models.CharField(max_length=120)
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    badge_text = models.CharField(max_length=80, blank=True, default='Free Shipping')

    class Meta:
        ordering = ('name', 'id')

    def clean(self):
        super().clean()
        if self.min_order_amount < 0:
            raise ValidationError("Minimum order amount cannot be negative.")

    def __str__(self):
        return self.name


class BuyXGetYOffer(ActivationWindowMixin):
    name = models.CharField(max_length=120)
    buy_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='buy_x_offers',
    )
    buy_category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='buy_x_offers',
    )
    buy_quantity = models.PositiveIntegerField(default=1)
    get_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='get_y_offers',
    )
    get_category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='get_y_offers',
    )
    get_quantity = models.PositiveIntegerField(default=1)
    badge_text = models.CharField(max_length=80, blank=True, default='Buy X Get Y')

    class Meta:
        ordering = ('name', 'id')

    def clean(self):
        super().clean()
        buy_targets = [self.buy_product_id, self.buy_category_id]
        get_targets = [self.get_product_id, self.get_category_id]
        if sum(bool(target) for target in buy_targets) != 1:
            raise ValidationError("Select exactly one buy target: product or category.")
        if sum(bool(target) for target in get_targets) != 1:
            raise ValidationError("Select exactly one get target: product or category.")
        if self.buy_quantity <= 0 or self.get_quantity <= 0:
            raise ValidationError("Buy and get quantities must be greater than zero.")

    def __str__(self):
        return self.name


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name='redemptions',
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='coupon_redemptions',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='coupon_redemptions',
    )
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-used_at', 'id')

    def __str__(self):
        return f"{self.coupon.code} - {self.user}"
