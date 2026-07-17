from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import FileField, ImageField
from PIL import Image, UnidentifiedImageError

from .models import AuditEvent
from .services import audit

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
IMAGE_MIMES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
IMAGE_FORMAT_EXTENSIONS = {
    'JPEG': {'.jpg', '.jpeg'}, 'PNG': {'.png'}, 'GIF': {'.gif'}, 'WEBP': {'.webp'},
}
IMAGE_FORMAT_MIMES = {
    'JPEG': {'', 'image/jpeg'}, 'PNG': {'', 'image/png'},
    'GIF': {'', 'image/gif'}, 'WEBP': {'', 'image/webp'},
}
MAX_IMAGE_DIMENSION = 12000
DOCUMENT_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
VIDEO_EXTENSIONS = {'.mp4', '.webm'}
FONT_EXTENSIONS = {'.ttf', '.otf', '.woff', '.woff2'}


def _reject(message, upload=None):
    audit('upload_rejected', category=AuditEvent.Category.SECURITY, success=False, metadata={'filename': Path(getattr(upload, 'name', '')).name, 'reason': message})
    raise ValidationError(message)


def _base(upload, extensions, max_bytes):
    filename = upload.name or ''
    if not filename or '\x00' in filename or len(filename) > 255:
        _reject('The filename is invalid.', upload)
    extension = Path(filename).suffix.lower()
    if extension not in extensions:
        _reject('This file extension is not allowed.', upload)
    if upload.size > max_bytes:
        _reject(f'File exceeds the {max_bytes // (1024 * 1024)} MB limit.', upload)
    return extension


def validate_image_upload(upload):
    extension = _base(upload, IMAGE_EXTENSIONS, 5 * 1024 * 1024)
    content_type = (getattr(upload, 'content_type', '') or '').lower()
    if content_type and content_type not in IMAGE_MIMES:
        _reject('The declared MIME type is not an allowed image type.', upload)
    try:
        position = upload.tell()
        image = Image.open(upload)
        image_format = (image.format or '').upper()
        if extension not in IMAGE_FORMAT_EXTENSIONS.get(image_format, set()):
            _reject('The image content does not match its file extension.', upload)
        if content_type not in IMAGE_FORMAT_MIMES.get(image_format, set()):
            _reject('The image content does not match its declared MIME type.', upload)
        if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
            _reject(f'Image dimensions may not exceed {MAX_IMAGE_DIMENSION} pixels.', upload)
        image.verify()
        upload.seek(position)
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        _reject('The uploaded image is corrupt or its content does not match an image.', upload)
    return upload


def validate_document_upload(upload):
    extension = _base(upload, DOCUMENT_EXTENSIONS, 5 * 1024 * 1024)
    if extension == '.pdf':
        position = upload.tell(); signature = upload.read(5); upload.seek(position)
        if signature != b'%PDF-':
            _reject('The uploaded PDF signature is invalid.', upload)
        if getattr(upload, 'content_type', '') not in ('', 'application/pdf'):
            _reject('The declared MIME type does not match a PDF.', upload)
    else:
        validate_image_upload(upload)
    return upload


def validate_video_upload(upload):
    extension = _base(upload, VIDEO_EXTENSIONS, 25 * 1024 * 1024)
    position = upload.tell(); header = upload.read(16); upload.seek(position)
    if extension == '.mp4' and b'ftyp' not in header:
        _reject('The MP4 signature is invalid.', upload)
    if extension == '.webm' and not header.startswith(b'\x1aE\xdf\xa3'):
        _reject('The WebM signature is invalid.', upload)
    return upload


def validate_font_upload(upload):
    extension = _base(upload, FONT_EXTENSIONS, 5 * 1024 * 1024)
    position = upload.tell(); header = upload.read(4); upload.seek(position)
    signatures = {'.woff': b'wOFF', '.woff2': b'wOF2', '.ttf': b'\x00\x01\x00\x00', '.otf': b'OTTO'}
    if header != signatures[extension]:
        _reject('The font signature does not match its extension.', upload)
    return upload


class SecureUploadFormMixin:
    """Validates newly uploaded model files; existing stored files are untouched."""
    def clean(self):
        cleaned = super().clean()
        for field_name, value in cleaned.items():
            if not value or not hasattr(value, 'chunks'):
                continue
            model_field = self._meta.model._meta.get_field(field_name)
            if isinstance(model_field, ImageField):
                validate_image_upload(value)
            elif isinstance(model_field, FileField):
                if field_name == 'video': validate_video_upload(value)
                elif field_name == 'font_file': validate_font_upload(value)
                else: validate_document_upload(value)
        return cleaned
