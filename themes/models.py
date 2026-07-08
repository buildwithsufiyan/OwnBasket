from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

HEADER_CHOICES = [
    ("header1", "Header 1"),
    ("header2", "Header 2"),
    ("header3", "Header 3"),
    ("header4", "Header 4"),
    ("header5", "Header 5"),
]

HERO_CHOICES = [
    ("hero1", "Hero 1"),
    ("hero2", "Hero 2"),
    ("hero3", "Hero 3"),
    ("hero4", "Hero 4"),
    ("hero5", "Hero 5"),
    ("hero_slider", "Hero Slider"),
    ("video_hero", "Video Hero"),
    ("split_hero", "Split Hero"),
]

CATEGORY_CHOICES = [
    ("layout1", "Layout 1"),
    ("layout2", "Layout 2"),
    ("layout3", "Layout 3"),
    ("layout4", "Layout 4"),
]

BRAND_CHOICES = [
    ("layout1", "Layout 1"),
    ("layout2", "Layout 2"),
    ("layout3", "Layout 3"),
]

PRODUCT_CARD_CHOICES = [
    ("card1", "Card 1"),
    ("card2", "Card 2"),
    ("card3", "Card 3"),
    ("card4", "Card 4"),
    ("card5", "Card 5"),
    ("card6", "Card 6"),
    ("amazon", "Amazon Style"),
    ("minimal", "Minimal"),
    ("luxury", "Luxury"),
    ("glass", "Glass"),
]

PRODUCT_DETAIL_CHOICES = [
    ("layout1", "Layout 1"),
    ("layout2", "Layout 2"),
    ("layout3", "Layout 3"),
    ("layout4", "Layout 4"),
]

CART_CHOICES = [
    ("layout1", "Layout 1"),
    ("layout2", "Layout 2"),
    ("layout3", "Layout 3"),
]

CHECKOUT_CHOICES = [
    ("layout1", "Layout 1"),
    ("layout2", "Layout 2"),
    ("layout3", "Layout 3"),
]

FOOTER_CHOICES = [
    ("footer1", "Footer 1"),
    ("footer2", "Footer 2"),
    ("footer3", "Footer 3"),
    ("footer4", "Footer 4"),
    ("footer5", "Footer 5"),
]

FOOTER_WIDTH_CHOICES = [
    ("container", "Contained"),
    ("fluid", "Full Width"),
]

FONT_CHOICES = [
    ("Poppins", "Poppins"),
    ("Inter", "Inter"),
    ("Outfit", "Outfit"),
    ("Montserrat", "Montserrat"),
    ("Nunito", "Nunito"),
    ("Lato", "Lato"),
    ("Raleway", "Raleway"),
    ("Roboto", "Roboto"),
    ("Oswald", "Oswald"),
    ("Playfair Display", "Playfair Display"),
    ("Merriweather", "Merriweather"),
    ("Bebas Neue", "Bebas Neue"),
    ("Caveat", "Caveat"),
    ("Pacifico", "Pacifico"),
    ("Great Vibes", "Great Vibes"),
    ("Dancing Script", "Dancing Script"),
]

BORDER_RADIUS_CHOICES = [
    ("0px", "0px"),
    ("5px", "5px"),
    ("10px", "10px"),
    ("15px", "15px"),
    ("20px", "20px"),
    ("25px", "25px"),
]

BUTTON_STYLE_CHOICES = [
    ("rounded", "Rounded"),
    ("square", "Square"),
    ("pill", "Pill"),
    ("outline", "Outline"),
    ("gradient", "Gradient"),
    ("glass", "Glass"),
]

ANIMATION_CHOICES = [
    ("none", "None"),
    ("fade", "Fade"),
    ("zoom", "Zoom"),
    ("slide", "Slide"),
    ("scale", "Scale"),
    ("flip", "Flip"),
]


class Theme(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=20, default="1.0")
    author = models.CharField(max_length=100, default="OwnBasket")
    preview_image = models.ImageField(
        upload_to="theme_previews/", blank=True, null=True
    )

    is_active = models.BooleanField(default=False)
    is_custom = models.BooleanField(default=False)

    # Layout Component Customizations
    header_layout = models.CharField(
        max_length=50, choices=HEADER_CHOICES, default="header1"
    )
    hero_layout = models.CharField(max_length=50, choices=HERO_CHOICES, default="hero1")
    category_layout = models.CharField(
        max_length=50, choices=CATEGORY_CHOICES, default="layout1"
    )
    brand_layout = models.CharField(
        max_length=50, choices=BRAND_CHOICES, default="layout1"
    )
    product_card_layout = models.CharField(
        max_length=50, choices=PRODUCT_CARD_CHOICES, default="card1"
    )
    product_detail_layout = models.CharField(
        max_length=50, choices=PRODUCT_DETAIL_CHOICES, default="layout1"
    )
    cart_layout = models.CharField(
        max_length=50, choices=CART_CHOICES, default="layout1"
    )
    checkout_layout = models.CharField(
        max_length=50, choices=CHECKOUT_CHOICES, default="layout1"
    )
    footer_layout = models.CharField(
        max_length=50, choices=FOOTER_CHOICES, default="footer1"
    )
    theme_folder = models.CharField(
        max_length=100, unique=True, help_text="Folder name inside themes directory"
    )
    template_mappings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapping of OwnBasket page types to imported HTML template files.",
    )

    # ----------------------------------------------------------------
    # Brand Colors
    # ----------------------------------------------------------------
    brand_primary_color = models.CharField(
        max_length=7,
        default="#ffb800",
        help_text="Primary brand color for major UI elements.",
    )
    brand_secondary_color = models.CharField(
        max_length=7,
        default="#232f3e",
        help_text="Secondary brand color used for accents and backgrounds.",
    )
    brand_accent_color = models.CharField(
        max_length=7,
        default="#ffb800",
        help_text="Accent color for special highlights and call-to-actions.",
    )

    # ----------------------------------------------------------------
    # Background Colors
    # ----------------------------------------------------------------
    bg_body_color = models.CharField(
        max_length=7,
        default="#f4f6f9",
        help_text="Main background color of the website body.",
    )
    bg_section_color = models.CharField(
        max_length=7,
        default="#ffffff",
        help_text="Background color for content sections.",
    )
    bg_card_color = models.CharField(
        max_length=7,
        default="#ffffff",
        help_text="Background color for cards and panels.",
    )
    bg_header_color = models.CharField(
        max_length=7,
        default="#ffffff",
        help_text="Background color of the site header.",
    )
    bg_footer_color = models.CharField(
        max_length=7,
        default="#232f3e",
        help_text="Background color of the site footer.",
    )

    # ----------------------------------------------------------------
    # Text Colors
    # ----------------------------------------------------------------
    text_primary_color = models.CharField(
        max_length=7,
        default="#1a1a1a",
        help_text="Primary text color for body content.",
    )
    text_secondary_color = models.CharField(
        max_length=7,
        default="#6c757d",
        help_text="Secondary text color for meta information and subtitles.",
    )
    text_heading_color = models.CharField(
        max_length=7,
        default="#212529",
        help_text="Color for all heading elements (h1, h2, etc.).",
    )
    text_link_color = models.CharField(
        max_length=7, default="#ffb800", help_text="Default color for hyperlinks."
    )
    text_link_hover_color = models.CharField(
        max_length=7, default="#e0a200", help_text="Color for hyperlinks on hover."
    )

    # ----------------------------------------------------------------
    # Button Colors
    # ----------------------------------------------------------------
    btn_primary_bg_color = models.CharField(
        max_length=7,
        default="#ffb800",
        help_text="Background color for primary buttons.",
    )
    btn_primary_hover_bg_color = models.CharField(
        max_length=7,
        default="#e0a200",
        help_text="Background color for primary buttons on hover.",
    )
    btn_secondary_bg_color = models.CharField(
        max_length=7,
        default="#343a40",
        help_text="Background color for secondary buttons.",
    )
    btn_secondary_hover_bg_color = models.CharField(
        max_length=7,
        default="#232f3e",
        help_text="Background color for secondary buttons on hover.",
    )

    # ----------------------------------------------------------------
    # Product Colors
    # ----------------------------------------------------------------
    product_price_color = models.CharField(
        max_length=7, default="#d92d20", help_text="Color for the main product price."
    )
    product_sale_price_color = models.CharField(
        max_length=7,
        default="#d92d20",
        help_text="Color for the sale price when a product is discounted.",
    )
    product_discount_badge_bg_color = models.CharField(
        max_length=7,
        default="#d92d20",
        help_text="Background color for the discount badge.",
    )
    product_discount_badge_text_color = models.CharField(
        max_length=7, default="#ffffff", help_text="Text color for the discount badge."
    )

    # ----------------------------------------------------------------
    # Status Colors
    # ----------------------------------------------------------------
    status_success_color = models.CharField(
        max_length=7,
        default="#039855",
        help_text="Color for success messages and indicators.",
    )
    status_warning_color = models.CharField(
        max_length=7, default="#f79009", help_text="Color for warnings and alerts."
    )
    status_danger_color = models.CharField(
        max_length=7,
        default="#d92d20",
        help_text="Color for error messages and danger actions.",
    )
    status_info_color = models.CharField(
        max_length=7, default="#007bff", help_text="Color for informational messages."
    )

    # ----------------------------------------------------------------
    # Border Colors
    # ----------------------------------------------------------------
    border_global_color = models.CharField(
        max_length=7,
        default="#eaecf0",
        help_text="Global border color for elements like cards and tables.",
    )
    border_input_color = models.CharField(
        max_length=7, default="#ced4da", help_text="Border color for form input fields."
    )
    border_card_color = models.CharField(
        max_length=7,
        default="#eaecf0",
        help_text="Specific border color for card elements.",
    )

    # ----------------------------------------------------------------
    # Component Styles: Buttons
    # ----------------------------------------------------------------
    btn_border_radius = models.PositiveIntegerField(
        default=8, help_text="Button border radius in pixels."
    )
    btn_padding = models.CharField(
        max_length=20,
        default="12px 20px",
        help_text="Button padding (e.g., '12px 20px').",
    )
    btn_font_size = models.PositiveIntegerField(
        default=16, help_text="Button font size in pixels."
    )
    btn_font_weight = models.PositiveIntegerField(
        default=700, help_text="Button font weight (e.g., 400, 700)."
    )
    btn_border_width = models.PositiveIntegerField(
        default=1, help_text="Button border width in pixels."
    )
    btn_border_style = models.CharField(
        max_length=10,
        default="solid",
        help_text="Button border style (solid, dashed, etc.).",
    )
    btn_hover_animation = models.CharField(
        max_length=20,
        default="translateY",
        help_text="Animation on hover (e.g., translateY, scale).",
    )
    btn_hover_scale = models.FloatField(
        default=1.05, help_text="Scale factor on hover (e.g., 1.05)."
    )
    btn_hover_shadow = models.CharField(
        max_length=100,
        default="0 8px 24px rgba(0, 0, 0, 0.1)",
        help_text="Box shadow on hover.",
    )

    # ----------------------------------------------------------------
    # Component Styles: Cards
    # ----------------------------------------------------------------
    card_border_radius = models.PositiveIntegerField(
        default=12, help_text="Card border radius in pixels."
    )
    card_border_width = models.PositiveIntegerField(
        default=1, help_text="Card border width in pixels."
    )
    # card_border_color is already defined as border_card_color
    card_box_shadow = models.CharField(
        max_length=100,
        default="0 8px 24px rgba(0, 0, 0, 0.06)",
        help_text="Card box shadow.",
    )
    card_hover_shadow = models.CharField(
        max_length=100,
        default="0 14px 30px rgba(0, 0, 0, 0.08)",
        help_text="Card box shadow on hover.",
    )
    card_hover_lift_effect = models.BooleanField(
        default=True, help_text="Enable/disable card lift effect on hover."
    )
    card_image_radius = models.PositiveIntegerField(
        default=0, help_text="Radius for top images in cards."
    )

    # ----------------------------------------------------------------
    # Component Styles: Forms
    # ----------------------------------------------------------------
    form_input_height = models.PositiveIntegerField(
        default=46, help_text="Height of form input fields in pixels."
    )
    form_input_border_radius = models.PositiveIntegerField(
        default=8, help_text="Input field border radius in pixels."
    )
    form_input_border_width = models.PositiveIntegerField(
        default=1, help_text="Input field border width in pixels."
    )
    form_input_focus_color = models.CharField(
        max_length=7, default="#ffb800", help_text="Border color of focused input."
    )
    form_placeholder_color = models.CharField(
        max_length=7, default="#6c757d", help_text="Color of placeholder text."
    )
    form_label_style = models.CharField(
        max_length=20,
        default="normal",
        help_text="Style of form labels (e.g., normal, bold).",
    )

    # ----------------------------------------------------------------
    # Component Styles: Badges
    # ----------------------------------------------------------------
    badge_radius = models.PositiveIntegerField(
        default=999, help_text="Badge border radius in pixels (999 for pill shape)."
    )
    badge_padding = models.CharField(
        max_length=20, default="6px 12px", help_text="Padding for badges."
    )
    badge_font_size = models.PositiveIntegerField(
        default=11, help_text="Font size for badges."
    )

    # ----------------------------------------------------------------
    # Component Styles: Tables
    # ----------------------------------------------------------------
    table_header_style = models.CharField(
        max_length=20,
        default="bold",
        help_text="Style of table headers (e.g., bold, uppercase).",
    )
    table_row_hover = models.BooleanField(
        default=True, help_text="Enable/disable row hover effect."
    )
    table_border_style = models.CharField(
        max_length=20,
        default="horizontal",
        help_text="Table border style (e.g., horizontal, all).",
    )

    # ----------------------------------------------------------------
    # Component Styles: Alerts
    # ----------------------------------------------------------------
    alert_radius = models.PositiveIntegerField(
        default=8, help_text="Alert box border radius in pixels."
    )
    alert_shadow = models.CharField(
        max_length=100,
        default="0 4px 12px rgba(0, 0, 0, 0.08)",
        help_text="Shadow for alert boxes.",
    )
    alert_padding = models.CharField(
        max_length=20, default="1rem", help_text="Padding for alerts."
    )

    # ----------------------------------------------------------------
    # Component Styles: Modal
    # ----------------------------------------------------------------
    modal_radius = models.PositiveIntegerField(
        default=16, help_text="Modal dialog border radius in pixels."
    )
    modal_shadow = models.CharField(
        max_length=100,
        default="0 14px 40px rgba(0, 0, 0, 0.15)",
        help_text="Shadow for modal dialogs.",
    )
    modal_width = models.PositiveIntegerField(
        default=500, help_text="Default width of modal dialogs in pixels."
    )

    # Typography & Radii & Animations
    font_family = models.CharField(max_length=50, choices=FONT_CHOICES, default="Inter")
    border_radius = models.CharField(
        max_length=10, choices=BORDER_RADIUS_CHOICES, default="10px"
    )
    button_style = models.CharField(
        max_length=20, choices=BUTTON_STYLE_CHOICES, default="rounded"
    )
    animation_style = models.CharField(
        max_length=20, choices=ANIMATION_CHOICES, default="none"
    )

    # --- Global Theme Settings ---
    # Layout & Spacing
    container_width = models.PositiveIntegerField(
        default=1200,
        help_text="Controls the max-width of primary layout containers (in pixels).",
    )
    section_spacing = models.PositiveIntegerField(
        default=60,
        help_text="Defines default top/bottom padding for major sections (in pixels).",
    )
    navbar_height = models.PositiveIntegerField(
        default=80,
        help_text="Specifies the height of the main navigation bar (in pixels).",
    )
    footer_width = models.CharField(
        max_length=20,
        choices=FOOTER_WIDTH_CHOICES,
        default="container",
        help_text="Determines if footer content is contained or spans the full width.",
    )

    # Borders & Shadows
    border_width = models.PositiveIntegerField(
        default=1, help_text="Defines the global border width for elements (in pixels)."
    )
    border_style = models.CharField(
        max_length=50,
        default="solid",
        help_text="Specifies the global border style (e.g., solid, dashed).",
    )
    image_border_radius = models.PositiveIntegerField(
        default=8, help_text="Controls the corner rounding for images (in pixels)."
    )
    input_border_radius = models.PositiveIntegerField(
        default=6, help_text="Sets the border radius for form inputs (in pixels)."
    )
    card_shadow = models.CharField(
        max_length=100,
        default="0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",
        help_text="Sets the box-shadow for card elements.",
    )
    button_shadow = models.CharField(
        max_length=100,
        default="0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        help_text="Adds a subtle shadow to buttons.",
    )

    # Animations & Interactivity
    global_transition_speed = models.CharField(
        max_length=20,
        default="0.3s",
        help_text="Sets a consistent duration for CSS transitions (e.g., 0.3s).",
    )
    hover_animation_style = models.CharField(
        max_length=50,
        default="scale",
        help_text="Defines a global hover effect (e.g., scale, lift, none).",
    )

    # Toggles & Features
    global_loader_toggle = models.BooleanField(
        default=True, help_text="Enable or disable the site-wide pre-loader animation."
    )
    scroll_to_top_toggle = models.BooleanField(
        default=True, help_text="Show or hide a 'scroll to top' button on long pages."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.theme_folder:
            self.theme_folder = self.slug
        if self.is_active:
            # Set other themes to inactive
            Theme.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @property
    def status_label(self):
        return "Active" if self.is_active else "Installed"

    def __str__(self):
        return f"{self.name} (v{self.version})"


@receiver(post_save, sender=Theme)
def invalidate_theme_cache(sender, instance, **kwargs):
    """
    Invalidates cache keys when a Theme object is saved.
    """
    # Always clear the specific preview cache for this theme
    cache.delete(f"preview_theme_{instance.pk}")

    # If this theme is the default theme, clear its cache
    if instance.slug == "default":
        cache.delete("default_theme")

    # If this theme is active, or if any theme is saved (because the previously
    # active one might have been deactivated by this save), clear the active_theme cache.
    # The `save()` method on the Theme model ensures only one theme can be active.
    # A simple approach is to always clear the active_theme cache on any save.
    # This is slightly less performant but guarantees correctness.
    cache.delete("active_theme")


class TemplateConversionLog(models.Model):
    """
    Logs suggestions for converting static HTML to Django templates.
    These are flagged for manual review by the user.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Review"
        APPLIED = "APPLIED", "Applied"
        REJECTED = "REJECTED", "Rejected"

    class ConversionType(models.TextChoices):
        VAR = "VAR", "Variable"
        LOOP = "LOOP", "For Loop"
        IMAGE = "IMAGE", "Image"
        URL = "URL", "URL"
        UNKNOWN = "UNKNOWN", "Unknown"
        WRAP = "WRAP", "Wrapper"

    theme = models.ForeignKey(
        Theme, on_delete=models.CASCADE, related_name="conversion_logs"
    )
    file_path = models.CharField(
        max_length=500, help_text="Path to the template file within the theme folder."
    )
    line_number = models.PositiveIntegerField(null=True, blank=True)
    target_selector = models.TextField(
        help_text="CSS selector to identify the target element for modification."
    )

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    conversion_type = models.CharField(
        max_length=10, choices=ConversionType.choices, default=ConversionType.UNKNOWN
    )

    original_html = models.TextField(help_text="The original HTML snippet.")
    suggested_code = models.TextField(help_text="The suggested Django template code.")

    confidence = models.FloatField(
        default=0.0, help_text="Confidence score of the suggestion (0.0 to 1.0)."
    )
    description = models.CharField(
        max_length=255, help_text="Explanation of the suggested change."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Template Conversion Suggestion"
        verbose_name_plural = "Template Conversion Suggestions"

    def __str__(self):
        return f"{self.get_status_display()} suggestion for {self.file_path} in {self.theme.name}"


class ThemeFileBackup(models.Model):
    """
    Stores versioned backups of theme files that have been modified.
    """

    theme = models.ForeignKey(
        Theme, on_delete=models.CASCADE, related_name="file_backups"
    )
    file_path = models.CharField(
        max_length=500, help_text="Path to the template file within the theme folder."
    )
    version = models.PositiveIntegerField()
    backup_file_path = models.CharField(
        max_length=1000, help_text="Path to the stored backup file."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    restored_from = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-version"]
        unique_together = ("theme", "file_path", "version")
        verbose_name = "Theme File Backup"
        verbose_name_plural = "Theme File Backups"

    def __str__(self):
        return f"v{self.version} of {self.file_path} for {self.theme.name}"
