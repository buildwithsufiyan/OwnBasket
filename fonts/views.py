from mimetypes import guess_type

from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from .models import ManagedFont
from .services import build_font_face_css, get_active_font_entries


@cache_control(public=True, max_age=3600)
@require_GET
def active_fonts_api(request):
    pack_slug = (request.GET.get('pack') or 'all-fonts').strip() or 'all-fonts'
    designer_slug = (request.GET.get('designer') or 'all-designer-fonts').strip() or 'all-designer-fonts'
    current_values = request.GET.getlist('current')
    payload = get_active_font_entries(
        current_values=current_values,
        pack_slug=pack_slug,
        designer_slug=designer_slug,
    )
    return JsonResponse({
        'pack': pack_slug,
        'designer': designer_slug,
        'results': payload,
    })


@cache_control(public=True, max_age=3600)
@require_GET
def managed_fonts_stylesheet(request):
    response = HttpResponse(build_font_face_css(), content_type='text/css; charset=utf-8')
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@cache_control(public=True, max_age=31536000, immutable=True)
@require_GET
def managed_font_file(request, pk):
    try:
        font = ManagedFont.objects.get(pk=pk, is_active=True, source='upload')
    except ManagedFont.DoesNotExist as exc:
        raise Http404('Font not found.') from exc

    if not font.font_file:
        raise Http404('Font file not found.')

    content_type = guess_type(font.font_file.name)[0] or 'application/octet-stream'
    response = FileResponse(font.font_file.open('rb'), content_type=content_type)
    response['Content-Disposition'] = f'inline; filename="{font.font_file.name.rsplit("/", 1)[-1]}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
