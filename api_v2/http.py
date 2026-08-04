import json
import hashlib
import logging
from functools import wraps
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, Paginator
from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.views.csrf import csrf_failure as django_csrf_failure


logger = logging.getLogger('api_v2')

MAX_BODY_BYTES = 64 * 1024


class ApiError(Exception):
    def __init__(self, code, message, status=400, fields=None):
        self.code = code
        self.message = message
        self.status = status
        self.fields = fields or {}
        super().__init__(message)


def error_response(code, message, status=400, fields=None):
    payload = {'error': {'code': code, 'message': message}}
    if fields:
        payload['error']['fields'] = fields
    return JsonResponse(payload, status=status)


def csrf_failure(request, reason=''):
    """Keep API failures machine-readable without changing website responses."""
    if request.path.startswith('/api/v2/'):
        return error_response(
            'csrf_failed',
            'A valid CSRF token is required for this request.',
            403,
        )
    return django_csrf_failure(request, reason=reason)


def _idempotency_record(request):
    from .models import IdempotencyRecord

    raw_key = request.headers.get('Idempotency-Key', '').strip()
    if not raw_key:
        if getattr(request, 'mobile_session', None):
            raise ApiError(
                'idempotency_key_required',
                'Bearer clients must send an Idempotency-Key for this operation.',
                400,
                {'Idempotency-Key': ['Use a unique value from 8 to 128 characters.']},
            )
        return None, None
    if len(raw_key) < 8 or len(raw_key) > 128 or any(ord(char) < 33 or ord(char) > 126 for char in raw_key):
        raise ApiError(
            'invalid_idempotency_key', 'Idempotency-Key is invalid.', 400,
            {'Idempotency-Key': ['Use 8 to 128 printable non-space ASCII characters.']},
        )
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    request_hash = hashlib.sha256(
        request.method.encode() + b'\0' + request.path.encode() + b'\0' + request.body
    ).hexdigest()
    defaults = {
        'method': request.method, 'path': request.path, 'request_hash': request_hash,
        'expires_at': timezone.now() + timedelta(hours=settings.API_IDEMPOTENCY_HOURS),
    }
    try:
        with transaction.atomic():
            record, created = IdempotencyRecord.objects.get_or_create(
                user=request.user, key_hash=key_hash, defaults=defaults,
            )
    except IntegrityError:
        record, created = IdempotencyRecord.objects.get(user=request.user, key_hash=key_hash), False
    if not created:
        if record.request_hash != request_hash or record.path != request.path or record.method != request.method:
            raise ApiError(
                'idempotency_conflict',
                'This Idempotency-Key was already used for a different request.',
                409,
            )
        if record.status == IdempotencyRecord.Status.COMPLETED:
            response = JsonResponse(record.response_body, status=record.response_status)
            response['Idempotency-Replayed'] = 'true'
            return record, response
        response = error_response('idempotency_in_progress', 'The original request is still processing.', 409)
        response['Retry-After'] = '2'
        return record, response
    return record, None


def _complete_idempotency(record, response):
    if not record:
        return
    from .models import IdempotencyRecord
    try:
        body = json.loads(response.content.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = {'error': {'code': 'unreplayable_response', 'message': 'The original response was not JSON.'}}
    IdempotencyRecord.objects.filter(pk=record.pk).update(
        status=IdempotencyRecord.Status.COMPLETED,
        response_status=response.status_code,
        response_body=body,
        completed_at=timezone.now(),
    )


def _release_idempotency(record):
    """Drop a still-processing record so a failed request can be retried."""
    from .models import IdempotencyRecord

    IdempotencyRecord.objects.filter(
        pk=record.pk, status=IdempotencyRecord.Status.PROCESSING
    ).delete()


def api_endpoint(
    methods=('GET',), *, auth=False, public_cache_seconds=0, idempotent=False,
    summary='', description='', tags=(), request_example=None, response_example=None,
):
    allowed = tuple(method.upper() for method in methods)

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in allowed:
                response = error_response('method_not_allowed', 'This method is not allowed.', 405)
                response['Allow'] = ', '.join(allowed)
                return response
            if auth and getattr(request, 'mobile_auth_error', None):
                response = error_response(request.mobile_auth_error, 'Bearer token is invalid or expired.', 401)
                response['WWW-Authenticate'] = 'Bearer realm="OwnBasket API", error="invalid_token"'
                return response
            if auth and not request.user.is_authenticated:
                response = error_response('authentication_required', 'Sign in is required for this endpoint.', 401)
                response['WWW-Authenticate'] = 'Bearer realm="OwnBasket API"'
                return response
            record = None
            owns_record = False
            try:
                if idempotent:
                    record, replay = _idempotency_record(request)
                    if replay:
                        response = replay
                    else:
                        owns_record = record is not None
                        response = view(request, *args, **kwargs)
                else:
                    response = view(request, *args, **kwargs)
            except ApiError as exc:
                response = error_response(exc.code, exc.message, exc.status, exc.fields)
            except Http404:
                response = error_response('not_found', 'The requested resource was not found.', 404)
            except ValidationError as exc:
                fields = getattr(exc, 'message_dict', None)
                response = error_response('validation_error', 'Submitted data is invalid.', 400, fields)
            except Exception:
                if owns_record:
                    logger.warning(
                        'Releasing in-progress idempotency record %s after an unhandled error on %s',
                        record.pk, request.path,
                    )
                    _release_idempotency(record)
                raise
            if not isinstance(response, JsonResponse):
                response = JsonResponse(response)
            if record and not response.has_header('Idempotency-Replayed'):
                _complete_idempotency(record, response)
            response.setdefault('X-Content-Type-Options', 'nosniff')
            response.setdefault('API-Version', '2.0')
            if auth or request.user.is_authenticated or not public_cache_seconds:
                response['Cache-Control'] = 'no-store'
            else:
                response['Cache-Control'] = f'public, max-age={public_cache_seconds}'
            patch_vary_headers(response, ('Accept', 'Cookie'))
            return response
        wrapped.api_contract = {
            'methods': allowed, 'auth': auth, 'idempotent': idempotent,
            'summary': summary or view.__name__.replace('_', ' ').title(),
            'description': description, 'tags': tuple(tags) or ('Mobile API',),
            'request_example': request_example, 'response_example': response_example,
        }
        return wrapped
    return decorator


def json_body(request):
    if len(request.body) > MAX_BODY_BYTES:
        raise ApiError('payload_too_large', 'Request body exceeds 64 KB.', 413)
    if not request.body:
        return {}
    if request.content_type != 'application/json':
        raise ApiError('unsupported_media_type', 'Use application/json.', 415)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ApiError('invalid_json', 'Request body must contain valid JSON.')
    if not isinstance(payload, dict):
        raise ApiError('invalid_json_shape', 'Request JSON must be an object.')
    return payload


def positive_int(value, *, name, default=None, maximum=None):
    if value in (None, ''):
        if default is not None:
            return default
        raise ApiError('validation_error', f'{name} is required.', fields={name: ['This field is required.']})
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ApiError('validation_error', f'{name} must be an integer.', fields={name: ['Enter a whole number.']})
    if result < 1 or (maximum is not None and result > maximum):
        message = f'Use a value from 1 to {maximum}.' if maximum else 'Use a positive value.'
        raise ApiError('validation_error', f'{name} is outside the allowed range.', fields={name: [message]})
    return result


def paginated(request, queryset, serializer, *, default_size=20, maximum_size=50, prepare=None):
    page_size = positive_int(request.GET.get('page_size'), name='page_size', default=default_size, maximum=maximum_size)
    page_number = positive_int(request.GET.get('page'), name='page', default=1)
    paginator = Paginator(queryset, page_size)
    try:
        page = paginator.page(page_number)
    except EmptyPage:
        raise ApiError('page_out_of_range', 'The requested page does not exist.', 404)
    objects = list(page.object_list)
    if prepare:
        objects = list(prepare(objects))
    return {
        'results': [serializer(item) for item in objects],
        'pagination': {
            'page': page.number,
            'pageSize': page_size,
            'totalPages': paginator.num_pages,
            'totalItems': paginator.count,
            'hasNext': page.has_next(),
            'hasPrevious': page.has_previous(),
        },
    }
