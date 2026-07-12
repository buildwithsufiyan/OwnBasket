from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from products.models import Brand, Category, Product


class SectionType(models.TextChoices):
    HERO = "hero", _("Hero Section")
    PRODUCT_CAROUSEL = "product_carousel", _("Product Carousel")
    FEATURED_CATEGORIES = "featured_categories", _("Featured Categories")
    FEATURED_BRANDS = "featured_brands", _("Featured Brands")
    BANNER = "banner", _("Banner Ad")


class HomepageSection(models.Model):
    """
    Base model for all homepage sections. It controls the common properties
    like ordering, activation status, and the type of section.
    """

    name = models.CharField(
        max_length=100, help_text="Internal name for this section in the admin."
    )
    section_type = models.CharField(
        max_length=50,
        choices=SectionType.choices,
        editable=False,
    )
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("display_order",)
        verbose_name = _("Homepage Section")
        verbose_name_plural = _("Homepage Sections")

    def __str__(self):
        return f"{self.name} ({self.get_section_type_display()})"

    def get_section_instance(self):
        """
        Dynamically gets the related concrete section instance (e.g., HeroSection).
        """
        accessor_map = {
            SectionType.HERO: "herosection",
            SectionType.PRODUCT_CAROUSEL: "productcarouselsection",
        }
        accessor_name = accessor_map.get(self.section_type)
        if not accessor_name:
            return None
        return getattr(self, accessor_name, None)


class HeroSection(HomepageSection):
    """
    A concrete implementation for a Hero section.
    """

    heading = models.CharField(max_length=150, blank=True)
    subheading = models.CharField(max_length=255, blank=True)
    background_image = models.ImageField(
        upload_to="site_sections/hero/", blank=True, null=True
    )
    background_color = models.CharField(max_length=20, default="#f4f6f9", blank=True)
    button_text = models.CharField(max_length=50, blank=True)
    button_url = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _("Hero Section")
        verbose_name_plural = _("Hero Sections")

    def save(self, *args, **kwargs):
        self.section_type = SectionType.HERO
        super().save(*args, **kwargs)

    @property
    def template_name(self):
        return "site_sections/hero_section.html"

    @property
    def has_content(self):
        return bool(self.heading or self.subheading or self.button_text)


class ProductCarouselSource(models.TextChoices):
    MANUAL = "manual", _("Manually Selected Products")
    FEATURED = "featured", _("Featured Products")
    LATEST = "latest", _("Latest Products")
    FLASH_SALE = "flash_sale", _("Flash Sale")
    DEAL_OF_THE_DAY = "deal_of_the_day", _("Deal of the Day")
    RECOMMENDED = "recommended", _("Recommended Products")
    CATEGORY = "category", _("Products from a Category")
    BRAND = "brand", _("Products from a Brand")
    # Retained for existing records; automatic calculations remain disabled.
    BEST_SELLING = "best_selling", _("Best Selling (legacy)")
    TRENDING = "trending", _("Trending (legacy)")


class ProductCarouselSection(HomepageSection):
    title = models.CharField(max_length=150, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    source_type = models.CharField(max_length=20, choices=ProductCarouselSource.choices, default=ProductCarouselSource.MANUAL)
    products_limit = models.PositiveIntegerField(default=8, help_text="Maximum products to display (1–48).")
    manual_products = models.ManyToManyField(Product, blank=True, related_name="product_carousels")
    category = models.ForeignKey(Category, blank=True, null=True, on_delete=models.SET_NULL)
    brand = models.ForeignKey(Brand, blank=True, null=True, on_delete=models.SET_NULL)
    # Legacy fields from the original carousel migration, retained for safe upgrades.
    button_text = models.CharField(max_length=50, blank=True)
    button_url = models.CharField(max_length=255, blank=True)
    background_color = models.CharField(max_length=20, blank=True)
    background_image = models.ImageField(upload_to="site_sections/carousels/", blank=True, null=True)
    layout_style = models.CharField(max_length=20, choices=(("slider", _("Slider")), ("grid", _("Grid"))), default="slider")
    show_view_all = models.BooleanField(default=False)
    view_all_text = models.CharField(max_length=40, blank=True, default="View all")
    view_all_url = models.CharField(max_length=255, blank=True)
    autoplay = models.BooleanField(default=False)
    loop = models.BooleanField(default=False)
    autoplay_speed = models.PositiveIntegerField(default=4500, help_text="Milliseconds (2000–15000).")
    show_navigation = models.BooleanField(default=True)
    show_pagination = models.BooleanField(default=False)
    show_on_mobile = models.BooleanField(default=True)
    show_on_desktop = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Product Carousel Section")
        verbose_name_plural = _("Product Carousel Sections")

    def save(self, *args, **kwargs):
        self.section_type = SectionType.PRODUCT_CAROUSEL
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        if not 1 <= self.products_limit <= 48:
            errors["products_limit"] = _("Use a value between 1 and 48.")
        if not 2000 <= self.autoplay_speed <= 15000:
            errors["autoplay_speed"] = _("Use a value between 2000 and 15000 milliseconds.")
        if self.source_type == ProductCarouselSource.CATEGORY and not self.category_id:
            errors["category"] = _("Choose a category for this source type.")
        if self.source_type == ProductCarouselSource.BRAND and not self.brand_id:
            errors["brand"] = _("Choose a brand for this source type.")
        if self.show_view_all and not self.view_all_url:
            errors["view_all_url"] = _("A View all URL is required when the button is enabled.")
        if errors:
            raise ValidationError(errors)
