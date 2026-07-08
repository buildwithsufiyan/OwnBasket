from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


FONT_CATEGORY_CHOICES = [
    ('script', 'Script'),
    ('sans-serif', 'Sans Serif'),
    ('serif', 'Serif'),
    ('handwriting', 'Handwriting'),
    ('display', 'Display'),
    ('monospace', 'Monospace'),
]

FONT_FILE_EXTENSIONS = ['ttf', 'otf', 'woff', 'woff2']
FONT_SOURCE_CHOICES = [
    ('upload', 'Uploaded Font'),
    ('google', 'Google Font'),
]
FONT_PACK_GROUP_CHOICES = [
    ('default', 'Default'),
    ('business', 'Business'),
    ('design', 'Design'),
    ('style', 'Style'),
    ('special', 'Special'),
]


def managed_font_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    base_name = slugify(instance.name or instance.css_name or Path(filename).stem) or 'font'
    return f'fonts/{base_name}{extension}'


def managed_font_preview_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    base_name = slugify(instance.name or instance.css_name or Path(filename).stem) or 'font-preview'
    return f'fonts/previews/{base_name}{extension}'


class ManagedFontPack(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name='Pack Name')
    slug = models.SlugField(max_length=180, unique=True, verbose_name='Pack Slug')
    group = models.CharField(
        max_length=20,
        choices=FONT_PACK_GROUP_CHOICES,
        default='default',
        verbose_name='Pack Group',
    )
    description = models.CharField(max_length=255, blank=True, verbose_name='Description')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sort Order')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    class Meta:
        verbose_name = 'Font Pack'
        verbose_name_plural = 'Font Packs'
        ordering = ['group', 'sort_order', 'name', 'id']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ManagedFont(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name='Font Name')
    css_name = models.CharField(max_length=180, verbose_name='CSS Font Family Name')
    source = models.CharField(
        max_length=20,
        choices=FONT_SOURCE_CHOICES,
        default='upload',
        verbose_name='Font Source',
    )
    google_family = models.CharField(
        max_length=180,
        blank=True,
        verbose_name='Google Font Family Name',
        help_text='Optional Google Fonts family name. Leave blank to use CSS Font Family Name.',
    )
    style_label = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='Preview Style Label',
        help_text='Short descriptor shown below the font name in the picker preview.',
    )
    font_file = models.FileField(
        upload_to=managed_font_upload_to,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=FONT_FILE_EXTENSIONS)],
        verbose_name='Font File',
        help_text='Upload .ttf, .otf, .woff, or .woff2 files. WOFF2 is recommended for best performance.',
    )
    category = models.CharField(
        max_length=20,
        choices=FONT_CATEGORY_CHOICES,
        default='sans-serif',
        verbose_name='Font Category',
    )
    preview_image = models.ImageField(
        upload_to=managed_font_preview_upload_to,
        blank=True,
        null=True,
        verbose_name='Preview Image',
    )
    packs = models.ManyToManyField(
        ManagedFontPack,
        through='ManagedFontPackFont',
        blank=True,
        related_name='fonts',
        verbose_name='Font Packs',
    )
    is_active = models.BooleanField(default=False, verbose_name='Active')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sort Order')
    usage_count = models.PositiveIntegerField(default=0, editable=False, verbose_name='Usage Count')
    last_used_at = models.DateTimeField(blank=True, null=True, editable=False, verbose_name='Last Used At')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')

    class Meta:
        verbose_name = 'Font'
        verbose_name_plural = 'Fonts'
        ordering = ['sort_order', 'name', 'id']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()

        if not self.css_name:
            self.css_name = self.name

        duplicate_css = ManagedFont.objects.exclude(pk=self.pk).filter(
            css_name__iexact=self.css_name.strip()
        )
        if duplicate_css.exists():
            raise ValidationError({'css_name': 'A font with this CSS font family name already exists.'})

        if self.source == 'google' and not self.google_family:
            self.google_family = self.css_name

        if self.is_active and self.source == 'upload' and not self.font_file:
            raise ValidationError({'font_file': 'Upload a font file before activating this font.'})

    def save(self, *args, **kwargs):
        if not self.css_name:
            self.css_name = self.name
        if self.source == 'google' and not self.google_family:
            self.google_family = self.css_name
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def file_extension(self):
        if not self.font_file:
            return ''
        return Path(self.font_file.name).suffix.lower().lstrip('.')

    @property
    def font_format(self):
        extension_map = {
            'ttf': 'truetype',
            'otf': 'opentype',
            'woff': 'woff',
            'woff2': 'woff2',
        }
        return extension_map.get(self.file_extension, '')

    @property
    def preview_url(self):
        if self.preview_image:
            return self.preview_image.url
        return ''

    @property
    def font_url(self):
        if self.source != 'upload' or not self.font_file:
            return ''
        return reverse('fonts:font-file', args=[self.pk])


class ManagedFontPackFont(models.Model):
    pack = models.ForeignKey(
        ManagedFontPack,
        on_delete=models.CASCADE,
        related_name='font_links',
    )
    font = models.ForeignKey(
        ManagedFont,
        on_delete=models.CASCADE,
        related_name='pack_links',
    )
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Sort Order')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')

    class Meta:
        verbose_name = 'Font Pack Item'
        verbose_name_plural = 'Font Pack Items'
        ordering = ['sort_order', 'id']
        unique_together = [('pack', 'font')]

    def __str__(self):
        return f'{self.pack.name} -> {self.font.name}'
