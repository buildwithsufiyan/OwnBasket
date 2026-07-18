import re

from django.http import JsonResponse
from django.shortcuts import render


PARAMETER_RE = re.compile(r'<(?:(?P<converter>[^:>]+):)?(?P<name>[^>]+)>')


def _path(route):
    return '/api/v2/' + PARAMETER_RE.sub(lambda match: '{' + match.group('name') + '}', str(route))


def _parameters(route):
    parameters = []
    for match in PARAMETER_RE.finditer(str(route)):
        converter = match.group('converter') or 'str'
        schema = {'type': 'integer', 'minimum': 1} if converter == 'int' else {'type': 'string'}
        parameters.append({'name': match.group('name'), 'in': 'path', 'required': True, 'schema': schema})
    return parameters


def build_spec(request):
    from .urls import urlpatterns

    paths = {}
    for pattern in urlpatterns:
        contract = getattr(pattern.callback, 'api_contract', None)
        if not contract:
            continue
        route = str(pattern.pattern)
        path_item = paths.setdefault(_path(route), {})
        for method in contract['methods']:
            operation = {
                'operationId': f"{pattern.name}_{method.lower()}".replace('-', '_'),
                'summary': contract['summary'],
                'description': contract['description'],
                'tags': list(contract['tags']),
                'parameters': _parameters(route),
                'responses': {
                    '200': {
                        'description': 'Successful response',
                        'content': {'application/json': {
                            'schema': {'type': 'object'},
                            'example': contract['response_example'] or {'status': 'ok'},
                        }},
                    },
                    '400': {'$ref': '#/components/responses/BadRequest'},
                    '429': {'$ref': '#/components/responses/RateLimited'},
                },
            }
            if contract['auth']:
                operation['security'] = [{'bearerAuth': []}, {'sessionCookie': []}]
                operation['responses']['401'] = {'$ref': '#/components/responses/Unauthorized'}
            if contract['idempotent']:
                operation['parameters'].append({
                    'name': 'Idempotency-Key', 'in': 'header',
                    'required': False,
                    'description': 'Required for Bearer clients. Session clients may provide it for replay safety.',
                    'schema': {'type': 'string', 'minLength': 8, 'maxLength': 128},
                    'example': 'checkout-550e8400-e29b-41d4-a716',
                })
                operation['responses']['409'] = {'$ref': '#/components/responses/Conflict'}
            if method in {'POST', 'PUT', 'PATCH'}:
                content = {'schema': {'type': 'object'}}
                content['example'] = contract['request_example'] or {}
                operation['requestBody'] = {'required': True, 'content': {'application/json': content}}
            path_item[method.lower()] = operation
    return {
        'openapi': '3.0.3',
        'info': {
            'title': 'OwnBasket Mobile API', 'version': '2.0.0',
            'description': (
                'Production mobile/PWA API v2. Bearer access tokens are short lived; refresh tokens rotate on every use. '
                'Existing same-origin session authentication remains supported with CSRF on unsafe methods.'
            ),
        },
        'servers': [{'url': request.build_absolute_uri('/').rstrip('/'), 'description': 'Current environment'}],
        'paths': paths,
        'components': {
            'securitySchemes': {
                'bearerAuth': {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'opaque'},
                'sessionCookie': {'type': 'apiKey', 'in': 'cookie', 'name': 'sessionid', 'description': 'Requires X-CSRFToken for unsafe methods.'},
            },
            'schemas': {
                'ApiError': {
                    'type': 'object', 'required': ['error'],
                    'example': {'error': {'code': 'validation_error', 'message': 'Submitted data is invalid.', 'fields': {'field': ['Reason']}}},
                    'properties': {'error': {'type': 'object', 'required': ['code', 'message'], 'properties': {
                        'code': {'type': 'string', 'example': 'validation_error'},
                        'message': {'type': 'string', 'example': 'Submitted data is invalid.'},
                        'fields': {'type': 'object', 'additionalProperties': {'type': 'array', 'items': {'type': 'string'}}},
                    }}},
                },
            },
            'responses': {
                'BadRequest': {'description': 'Invalid input', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/ApiError'}}}},
                'Unauthorized': {'description': 'Authentication required or token invalid', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/ApiError'}}}},
                'Conflict': {'description': 'Idempotency or synchronization conflict', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/ApiError'}}}},
                'RateLimited': {'description': 'Rate limit exceeded', 'headers': {'Retry-After': {'schema': {'type': 'integer'}}}, 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/ApiError'}}}},
            },
        },
    }


def schema(request):
    response = JsonResponse(build_spec(request))
    response['Cache-Control'] = 'public, max-age=300'
    response['API-Version'] = '2.0'
    return response


def swagger_ui(request):
    response = render(request, 'api_v2/swagger.html')
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


def redoc_ui(request):
    response = render(request, 'api_v2/redoc.html')
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response
