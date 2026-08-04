from django.utils.http import url_has_allowed_host_and_scheme


def safe_redirect_target(request, candidate, fallback, extra_hosts=()):
    """Return ``candidate`` when it is a safe redirect target, otherwise ``fallback``."""
    allowed_hosts = {request.get_host(), *(host for host in extra_hosts if host)}
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts=allowed_hosts, require_https=request.is_secure(),
    ):
        return candidate
    return fallback
