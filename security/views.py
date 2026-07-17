from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import PrivacyRequestForm, SecuritySettingsForm
from .models import AccountSecurityState, AuditEvent, PrivacyRequest, SecurityAlert, TwoFactorProfile, UserSession
from .services import audit, session_hash


@staff_member_required
def security_dashboard(request):
    if not (request.user.is_superuser or request.user.has_perm('security.view_security_dashboard')):
        raise PermissionDenied
    since = timezone.now() - timedelta(hours=24)
    context = {
        'failed_logins': AuditEvent.objects.filter(action='login_failed', timestamp__gte=since).count(),
        'successful_logins': AuditEvent.objects.filter(action='login', success=True, timestamp__gte=since).count(),
        'locked_accounts': AccountSecurityState.objects.filter(locked_until__gt=timezone.now()).count(),
        'active_sessions': UserSession.objects.filter(ended_at__isnull=True, last_active__gte=timezone.now() - timedelta(minutes=30)).count(),
        'open_alerts': SecurityAlert.objects.filter(resolved=False).count(),
        'upload_failures': AuditEvent.objects.filter(action='upload_rejected', timestamp__gte=since).count(),
        'recent_events': AuditEvent.objects.select_related('user')[:50],
        'alerts': SecurityAlert.objects.filter(resolved=False).select_related('user')[:20],
    }
    return render(request, 'security/dashboard.html', context)


@login_required
def security_center(request):
    two_factor, _ = TwoFactorProfile.objects.get_or_create(user=request.user)
    current_hash = session_hash(request.session.session_key)
    sessions = request.user.security_sessions.order_by('-last_active')[:50]
    history = request.user.audit_events.filter(category=AuditEvent.Category.AUTH)[:30]
    return render(request, 'security/center.html', {
        'sessions': sessions, 'current_hash': current_hash, 'login_history': history,
        'two_factor': two_factor,
    })


@login_required
@require_POST
def logout_other_sessions(request):
    current_hash = session_hash(request.session.session_key)
    target_hashes = set(request.user.security_sessions.filter(ended_at__isnull=True).exclude(session_key_hash=current_hash).values_list('session_key_hash', flat=True))
    deleted = 0
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator(chunk_size=500):
        if session_hash(session.session_key) in target_hashes:
            session.delete(); deleted += 1
    request.user.security_sessions.filter(session_key_hash__in=target_hashes).update(ended_at=timezone.now())
    audit('logout_other_sessions', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request, metadata={'sessions_ended': deleted})
    return redirect('security:center')


@login_required
@require_POST
def revoke_session(request, session_id):
    tracked = get_object_or_404(UserSession, pk=session_id, user=request.user, ended_at__isnull=True)
    current_hash = session_hash(request.session.session_key)
    if tracked.session_key_hash == current_hash:
        audit('current_session_revocation_blocked', category=AuditEvent.Category.SECURITY, user=request.user, request=request, success=False)
        return redirect('security:center')
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator(chunk_size=500):
        if session_hash(session.session_key) == tracked.session_key_hash:
            session.delete()
            break
    tracked.ended_at = timezone.now()
    tracked.save(update_fields=('ended_at',))
    audit('session_revoked', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request, metadata={'tracked_session_id': tracked.pk})
    return redirect('security:center')


@login_required
@require_POST
def two_factor_opt_in(request):
    form = SecuritySettingsForm(request.POST)
    profile, _ = TwoFactorProfile.objects.get_or_create(user=request.user)
    if form.is_valid() and request.user.check_password(form.cleaned_data['password']) and request.user.email:
        profile.opted_in = True
        profile.method = profile.Method.EMAIL
        profile.verified_at = None
        profile.save(update_fields=('opted_in', 'method', 'verified_at', 'updated_at'))
        audit('two_factor_opt_in', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request)
    else:
        audit('two_factor_opt_in_failed', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request, success=False)
    return redirect('security:center')


@login_required
@require_POST
def two_factor_opt_out(request):
    form = SecuritySettingsForm(request.POST)
    if form.is_valid() and request.user.check_password(form.cleaned_data['password']):
        profile, _ = TwoFactorProfile.objects.get_or_create(user=request.user)
        profile.opted_in = False
        profile.verified_at = None
        profile.save(update_fields=('opted_in', 'verified_at', 'updated_at'))
        audit('two_factor_opt_out', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request)
    return redirect('security:center')


@login_required
def privacy_requests(request):
    form = PrivacyRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            privacy_request = form.save(commit=False)
            privacy_request.user = request.user
            privacy_request.status = PrivacyRequest.Status.PENDING
            privacy_request.save()
            audit('privacy_request_created', category=AuditEvent.Category.COMPLIANCE, user=request.user, request=request, obj=privacy_request)
        return redirect('security:privacy_requests')
    return render(request, 'security/privacy_requests.html', {'form': form, 'requests': request.user.privacy_requests.all()[:30]})
