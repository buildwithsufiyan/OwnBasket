from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class HomepageCarousel(models.Model):
    image = models.ImageField(upload_to='homepage/carousel/', verbose_name="Carousel Image")
    title = models.CharField(max_length=120, blank=True, verbose_name="Slide Title")
    redirect_url = models.URLField(max_length=500, blank=True, verbose_name="Redirect URL")
    display_order = models.PositiveIntegerField(default=0, verbose_name="Display Order")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    slide_duration = models.PositiveIntegerField(default=5000, verbose_name="Slide Duration (ms)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Date")

    class Meta:
        verbose_name = "Homepage Carousel"
        verbose_name_plural = "Homepage Carousels"
        ordering = ['display_order', 'created_at', 'id']

    def __str__(self):
        return self.title or f"Carousel Slide {self.id}"


class BannerCarousel(models.Model):
    LAYOUT_CHOICES = [
        ('layout_1', 'Layout 1 = Text Left + Image Right'),
        ('layout_2', 'Layout 2 = Image Left + Text Right'),
        ('layout_3', 'Layout 3 = Center Content'),
        ('layout_4', 'Layout 4 = Full Background Banner'),
        ('layout_5', 'Layout 5 = Right Image with Overlay Text'),
        ('layout_6', 'Layout 6 = Left Image with Overlay Text'),
        ('layout_7', 'Layout 7 = Split Text + Center Image'),
    ]

    ANIMATION_CHOICES = [
        ('none', 'None'),
        ('fade-in', 'Fade In'),
        ('fade-up', 'Fade Up'),
        ('fade-down', 'Fade Down'),
        ('slide-left', 'Slide Left'),
        ('slide-right', 'Slide Right'),
        ('zoom-in', 'Zoom In'),
        ('zoom-out', 'Zoom Out'),
        ('bounce', 'Bounce'),
        ('pulse', 'Pulse'),
    ]

    BACKGROUND_TYPE_CHOICES = [
        ('solid', 'Solid Color'),
        ('gradient', 'Gradient'),
        ('image', 'Image Background'),
    ]

    BUTTON_STYLE_CHOICES = [
        ('solid', 'Solid'),
        ('outline', 'Outline'),
        ('rounded', 'Rounded'),
        ('pill', 'Pill'),
        ('ghost', 'Ghost'),
    ]

    GRADIENT_DIRECTION_CHOICES = [
        ('to right', 'Left to Right'),
        ('to left', 'Right to Left'),
        ('to bottom', 'Top to Bottom'),
        ('to top', 'Bottom to Top'),
        ('45deg', 'Diagonal'),
    ]

    image = models.ImageField(upload_to='homepage/hero-carousel/', verbose_name="Slide Image")
    badge_text = models.CharField(max_length=60, blank=True, verbose_name="Badge Text")
    heading = models.CharField(max_length=160, verbose_name="Heading")
    description = models.CharField(max_length=260, blank=True, verbose_name="Description")
    button_text = models.CharField(max_length=80, blank=True, verbose_name="Button Text")
    button_url = models.URLField(max_length=500, blank=True, verbose_name="Button URL")

    show_badge = models.BooleanField(default=True, verbose_name="Show Badge")
    show_heading = models.BooleanField(default=True, verbose_name="Show Heading")
    show_description = models.BooleanField(default=True, verbose_name="Show Description")
    show_button = models.BooleanField(default=True, verbose_name="Show Button")
    show_image = models.BooleanField(default=True, verbose_name="Show Image")
    show_left_content = models.BooleanField(default=True, verbose_name="Show Left Content")
    show_right_content = models.BooleanField(default=True, verbose_name="Show Right Content")
    show_on_desktop = models.BooleanField(default=True, verbose_name="Show on Desktop")
    show_on_tablet = models.BooleanField(default=True, verbose_name="Show on Tablet")
    show_on_mobile = models.BooleanField(default=True, verbose_name="Show on Mobile")

    left_badge_text = models.CharField(max_length=60, blank=True, verbose_name="Left Badge Text")
    left_heading = models.CharField(max_length=160, blank=True, verbose_name="Left Heading")
    left_description = models.CharField(max_length=260, blank=True, verbose_name="Left Description")
    left_button_text = models.CharField(max_length=80, blank=True, verbose_name="Left Button Text")
    left_button_url = models.URLField(max_length=500, blank=True, verbose_name="Left Button URL")

    right_badge_text = models.CharField(max_length=60, blank=True, verbose_name="Right Badge Text")
    right_heading = models.CharField(max_length=160, blank=True, verbose_name="Right Heading")
    right_description = models.CharField(max_length=260, blank=True, verbose_name="Right Description")
    right_button_text = models.CharField(max_length=80, blank=True, verbose_name="Right Button Text")
    right_button_url = models.URLField(max_length=500, blank=True, verbose_name="Right Button URL")

    layout_template = models.CharField(
        max_length=30,
        choices=LAYOUT_CHOICES,
        default='layout_1',
        verbose_name="Banner Layout Template"
    )

    badge_font_size = models.CharField(max_length=20, default='0.8rem', verbose_name="Badge Font Size")
    badge_font_family = models.CharField(max_length=100, default='Inter', verbose_name="Badge Font Family")
    badge_font_weight = models.CharField(max_length=20, default='700', verbose_name="Badge Font Weight")
    badge_text_color = models.CharField(max_length=20, default='#ffffff', verbose_name="Badge Text Color")
    heading_font_size = models.CharField(max_length=30, default='clamp(2rem, 4vw, 3.5rem)', verbose_name="Heading Font Size")
    heading_font_family = models.CharField(max_length=100, default='Inter', verbose_name="Heading Font Family")
    heading_font_weight = models.CharField(max_length=20, default='700', verbose_name="Heading Font Weight")
    heading_text_color = models.CharField(max_length=20, default='#111827', verbose_name="Heading Text Color")
    description_font_size = models.CharField(max_length=20, default='1rem', verbose_name="Description Font Size")
    description_font_family = models.CharField(max_length=100, default='Inter', verbose_name="Description Font Family")
    description_font_weight = models.CharField(max_length=20, default='400', verbose_name="Description Font Weight")
    description_text_color = models.CharField(max_length=20, default='#4b5563', verbose_name="Description Text Color")

    button_border_radius = models.PositiveIntegerField(default=8, verbose_name="Button Border Radius")
    button_width = models.CharField(max_length=20, default='auto', verbose_name="Button Width")
    button_height = models.CharField(max_length=20, default='auto', verbose_name="Button Height")
    button_padding = models.CharField(max_length=40, default='0.75rem 1.25rem', verbose_name="Button Padding")
    button_font_size = models.CharField(max_length=20, default='0.95rem', verbose_name="Button Font Size")
    button_font_family = models.CharField(max_length=100, default='Inter', verbose_name="Button Font Family")
    button_font_weight = models.CharField(max_length=20, default='600', verbose_name="Button Font Weight")
    button_text_color = models.CharField(max_length=20, default='#ffffff', verbose_name="Button Text Color")
    button_background_color = models.CharField(max_length=20, default='#ffb800', verbose_name="Button Background Color")
    button_border_color = models.CharField(max_length=20, default='#ffb800', verbose_name="Button Border Color")
    button_hover_background_color = models.CharField(max_length=20, default='#e19c00', verbose_name="Hover Background Color")
    button_hover_text_color = models.CharField(max_length=20, default='#ffffff', verbose_name="Hover Text Color")
    button_hover_border_color = models.CharField(max_length=20, default='#e19c00', verbose_name="Hover Border Color")
    button_hover_shadow = models.BooleanField(default=True, verbose_name="Hover Shadow")
    button_variant = models.CharField(max_length=20, choices=BUTTON_STYLE_CHOICES, default='solid', verbose_name="Button Style")

    background_type = models.CharField(max_length=20, choices=BACKGROUND_TYPE_CHOICES, default='solid', verbose_name="Background Type")
    background_color = models.CharField(max_length=20, default='#f3f4f6', verbose_name="Background Color")
    background_gradient_color_1 = models.CharField(max_length=20, default='#f8fafc', verbose_name="Gradient Color 1")
    background_gradient_color_2 = models.CharField(max_length=20, default='#e2e8f0', verbose_name="Gradient Color 2")
    background_gradient_direction = models.CharField(max_length=20, choices=GRADIENT_DIRECTION_CHOICES, default='to right', verbose_name="Gradient Direction")
    background_image = models.ImageField(upload_to='homepage/hero-backgrounds/', blank=True, null=True, verbose_name="Background Image")
    background_position = models.CharField(max_length=30, default='center center', verbose_name="Background Position")
    background_size = models.CharField(max_length=20, default='cover', verbose_name="Background Size")
    background_repeat = models.CharField(max_length=20, default='no-repeat', verbose_name="Background Repeat")
    enable_overlay = models.BooleanField(default=True, verbose_name="Enable Overlay")
    background_overlay_color = models.CharField(max_length=20, default='#111827', verbose_name="Overlay Color")
    background_overlay_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.20, verbose_name="Overlay Opacity")

    badge_animation = models.CharField(max_length=20, choices=ANIMATION_CHOICES, default='none', verbose_name="Badge Animation")
    heading_animation = models.CharField(max_length=20, choices=ANIMATION_CHOICES, default='none', verbose_name="Heading Animation")
    description_animation = models.CharField(max_length=20, choices=ANIMATION_CHOICES, default='none', verbose_name="Description Animation")
    button_animation = models.CharField(max_length=20, choices=ANIMATION_CHOICES, default='none', verbose_name="Button Animation")
    image_animation = models.CharField(max_length=20, choices=ANIMATION_CHOICES, default='none', verbose_name="Image Animation")
    animation_duration = models.PositiveIntegerField(default=800, verbose_name="Animation Duration (ms)")
    animation_delay = models.PositiveIntegerField(default=0, verbose_name="Animation Delay (ms)")

    views_count = models.PositiveIntegerField(default=0, verbose_name="Banner Views")
    clicks_count = models.PositiveIntegerField(default=0, verbose_name="Banner Clicks")

    display_order = models.PositiveIntegerField(default=0, verbose_name="Display Order")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    slide_duration = models.PositiveIntegerField(default=5000, verbose_name="Slide Duration (ms)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Date")

    class Meta:
        verbose_name = "Hero Banner Carousel"
        verbose_name_plural = "Hero Banner Carousels"
        ordering = ['display_order', 'created_at', 'id']

    def __str__(self):
        return self.heading or f"Hero Slide {self.id}"

    @property
    def ctr_percentage(self):
        if self.views_count <= 0:
            return 0.0
        return round((self.clicks_count / self.views_count) * 100, 1)

    @property
    def ctr_display(self):
        return f"{self.ctr_percentage:.1f}%"

    @property
    def badge_animation_class(self):
        return self.get_animation_class('badge')

    @property
    def heading_animation_class(self):
        return self.get_animation_class('heading')

    @property
    def description_animation_class(self):
        return self.get_animation_class('description')

    @property
    def button_animation_class(self):
        return self.get_animation_class('button')

    @property
    def image_animation_class(self):
        return self.get_animation_class('image')

    @property
    def button_css_style(self):
        styles = [
            f"border-radius:{self.button_border_radius}px;",
            f"width:{self.button_width};",
            f"height:{self.button_height};",
            f"padding:{self.button_padding};",
            f"font-size:{self.button_font_size};",
            f"font-family:'{self.button_font_family}', sans-serif;",
            f"font-weight:{self.button_font_weight};",
            f"color:{self.button_text_color};",
            f"background-color:{self.button_background_color};",
            f"border:1px solid {self.button_border_color};",
            f"--hero-hover-bg:{self.button_hover_background_color};",
            f"--hero-hover-text:{self.button_hover_text_color};",
            f"--hero-hover-border:{self.button_hover_border_color};",
        ]
        if self.button_hover_shadow:
            styles.append("box-shadow:0 10px 30px rgba(0,0,0,0.12);")
        return " ".join(styles)

    @property
    def background_css_style(self):
        if self.background_type == 'gradient':
            return (
                f"background:linear-gradient({self.background_gradient_direction}, {self.background_gradient_color_1}, {self.background_gradient_color_2});"
            )
        if self.background_type == 'image' and self.background_image:
            return (
                f"background-image:url('{self.background_image.url}'); background-position:{self.background_position}; "
                f"background-size:{self.background_size}; background-repeat:{self.background_repeat};"
            )
        return f"background-color:{self.background_color};"

    @property
    def overlay_css_style(self):
        if not self.enable_overlay:
            return ""
        if self.background_type == 'image':
            return (
                f"background-color:{self.background_overlay_color}; opacity:{self.background_overlay_opacity};"
            )
        return f"background-color:{self.background_overlay_color}; opacity:{self.background_overlay_opacity};"

    def get_animation_class(self, element_name='heading'):
        animation_name = getattr(self, f"{element_name}_animation", 'none')
        if not animation_name or animation_name == 'none':
            return ''
        return f"hero-animate hero-animate-{animation_name}"

    def duplicate(self):
        duplicate = BannerCarousel.objects.get(pk=self.pk)
        duplicate.pk = None
        duplicate._state.adding = True
        duplicate.heading = f"{self.heading} Copy" if self.heading else "Banner Copy"
        duplicate.views_count = 0
        duplicate.clicks_count = 0
        duplicate.is_active = False
        duplicate.display_order = 0
        duplicate.created_at = None
        duplicate.updated_at = None
        duplicate.save()
        return duplicate


class HomepageSettings(models.Model):
    show_top_brands = models.BooleanField(
        default=True,
        verbose_name="Top Brands Enable"
    )
    show_categories = models.BooleanField(
        default=True,
        verbose_name="Categories Enable"
    )
    hero_badge_text = models.CharField(
        max_length=120,
        blank=True,
        default="UP TO 50% OFF",
        verbose_name="Small Badge Text"
    )
    hero_heading = models.CharField(
        max_length=200,
        default="UPCOMING SOON",
        verbose_name="Main Heading"
    )
    hero_subheading = models.CharField(
        max_length=300,
        blank=True,
        default="Your One-Stop Online Shopping Destination",
        verbose_name="Sub Heading"
    )
    hero_button_text = models.CharField(
        max_length=80,
        default="Stay Tuned!",
        verbose_name="Button Text"
    )
    hero_button_link = models.CharField(
        max_length=255,
        blank=True,
        default="/home/",
        verbose_name="Button Link"
    )
    hero_image = models.ImageField(
        upload_to='homepage/hero/',
        blank=True,
        null=True,
        verbose_name="Hero Image / Icon Upload"
    )
    hero_background_color = models.CharField(
        max_length=20,
        default="#f3f4f6",
        verbose_name="Hero Background Color"
    )
    promo_small_text = models.CharField(
        max_length=120,
        blank=True,
        default="THIS WEBSITE IS",
        verbose_name="Promotional Small Text"
    )
    promo_main_heading = models.CharField(
        max_length=200,
        default="UPCOMING SOON",
        verbose_name="Promotional Main Heading"
    )
    promo_tagline = models.CharField(
        max_length=200,
        blank=True,
        default="STAY TUNED!",
        verbose_name="Promotional Tagline"
    )
    promo_developer_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Developer Name"
    )
    promo_email = models.EmailField(
        blank=True,
        verbose_name="Email"
    )
    promo_contact_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Contact Number"
    )
    promo_image = models.ImageField(
        upload_to='homepage/promo/',
        blank=True,
        null=True,
        verbose_name="Right Side Image"
    )
    promo_background_color = models.CharField(
        max_length=20,
        default="#ffb800",
        verbose_name="Promotional Banner Background Color"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Homepage Settings"
        verbose_name_plural = "Homepage Settings"

    def __str__(self):
        return "Homepage Settings"

    def clean(self):
        if HomepageSettings.objects.exclude(pk=self.pk).exists():
            raise ValidationError("Only one Homepage Settings entry is allowed.")

    @classmethod
    def get_solo(cls):
        return cls.objects.order_by('pk').first() or cls()

    @property
    def resolved_hero_button_link(self):
        return self.hero_button_link or reverse('home')


class HomepageFeature(models.Model):
    ICON_CHOICES = [
        ('bi-truck', 'Truck'),
        ('bi-shield-check', 'Shield Check'),
        ('bi-arrow-repeat', 'Arrow Repeat'),
        ('bi-headset', 'Headset'),
        ('bi-credit-card', 'Credit Card'),
        ('bi-gift', 'Gift'),
        ('bi-box-seam', 'Box'),
        ('bi-star', 'Star'),
        ('bi-patch-check', 'Patch Check'),
    ]

    icon = models.CharField(
        max_length=50,
        choices=ICON_CHOICES,
        default='bi-truck',
        verbose_name="Icon"
    )
    title = models.CharField(max_length=100, verbose_name="Title")
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Description"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Display Order"
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Homepage Feature"
        verbose_name_plural = "Homepage Features"
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.title


class HomepageCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="Category Name")
    image = models.ImageField(
        upload_to='homepage/categories/',
        blank=True,
        null=True,
        verbose_name="Icon / Image"
    )
    linked_category = models.ForeignKey(
        'products.Category',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='homepage_categories',
        verbose_name="Linked Product Category"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Display Order"
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Homepage Category"
        verbose_name_plural = "Homepage Categories"
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name

    @property
    def target_url(self):
        if self.linked_category_id:
            return f"{reverse('home')}?category={self.linked_category.slug}"
        return reverse('home')
