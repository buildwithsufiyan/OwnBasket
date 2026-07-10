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


class ProductCarouselSection(HomepageSection):
    """
    A dynamic product carousel section for the homepage.
    Can source products manually or based on dynamic rules.
    """

    class SourceType(models.TextChoices):
        MANUAL = "manual", _("Manually Selected Products")
        FEATURED = "featured", _("All Featured Products")
        FLASH_SALE = "flash_sale", _("All Flash Sale Products")
        LATEST = "latest", _("Latest Products")
        BEST_SELLING = "best_selling", _("Best Selling Products")
        TRENDING = "trending", _("Trending Products (Most Views)")
        CATEGORY = "category", _("Products from a Category")
        BRAND = "brand", _("Products from a Brand")

    class LayoutStyle(models.TextChoices):
        SLIDER = "slider", _("Slider")
        GRID = "grid", _("Grid")

    title = models.CharField(max_length=150, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)

    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.MANUAL,
        help_text=_("How to source products for this carousel."),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("Required if source type is 'Category'."),
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("Required if source type is 'Brand'."),
    )
    manual_products = models.ManyToManyField(
        Product,
        blank=True,
        help_text=_("Required if source type is 'Manual'."),
        related_name="product_carousels",
    )
    products_limit = models.PositiveIntegerField(
        default=8, help_text=_("Maximum number of products to display.")
    )

    button_text = models.CharField(max_length=50, blank=True)
    button_url = models.CharField(max_length=255, blank=True)

    background_color = models.CharField(max_length=20, blank=True)
    background_image = models.ImageField(
        upload_to="site_sections/carousels/", blank=True, null=True
    )
    layout_style = models.CharField(
        max_length=20, choices=LayoutStyle.choices, default=LayoutStyle.SLIDER
    )

    class Meta:
        verbose_name = _("Product Carousel Section")
        verbose_name_plural = _("Product Carousel Sections")

    def save(self, *args, **kwargs):
        self.section_type = SectionType.PRODUCT_CAROUSEL
        super().save(*args, **kwargs)


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
