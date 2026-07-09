from django.db import models
from django.utils.translation import gettext_lazy as _


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
        return getattr(self, self.section_type, None)


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
