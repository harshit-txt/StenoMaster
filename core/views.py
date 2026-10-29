"""
core/views.py - everything a STUDENT sees.  (Owner/admin pages are in owner_views.py.)

Sections:
    1. small helpers
    2. landing / register / login / logout
    3. practice home, dashboard, assignment lists
    4. the 3-phase assignment flow  (listen -> reading -> typing -> submit -> result)
    5. weak words
    6. profile
"""
import time
from collections import Counter

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Max, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import stats
from .accounts import create_account, find_user_by_identifier, is_owner, normalize_phone, set_password
from .checker import ERROR_LIMITS, compare_texts, weak_word_candidates
from .forms import LoginForm, PasswordForm, ProfileForm, RegisterForm
from .models import Assignment, Submission, WeakWord


# ==========================================================================
#  1. Helpers
# ==========================================================================
def _home_for(user):
    """Where to send someone right after login."""
    return 'owner_dashboard' if is_owner(user) else 'practice'


def _paginate(request, queryset, per_page):
    return Paginator(queryset, per_page).get_page(request.GET.get('page'))


def _typing_key(pk):
    return f'typing_start_{pk}'          # session key that remembers when typing began


def _clamp(value, low, high, default):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


# ---- login lock-out (stops people guessing passwords) --------------------
def _throttle_keys(request, identifier):
    ident = normalize_phone(identifier) or identifier.strip().lower()
    return f'login-fail:id:{ident}', f'login-fail:ip:{request.META.get("REMOTE_ADDR", "")}'


def _is_locked(request, identifier):
    id_key, ip_key = _throttle_keys(request, identifier)
    return (cache.get(id_key, 0) >= settings.LOGIN_MAX_ATTEMPTS
            or cache.get(ip_key, 0) >= settings.LOGIN_MAX_ATTEMPTS * 5)   # IP limit is higher: a class may share one wifi


def _record_failure(request, identifier):
    timeout = settings.LOGIN_LOCKOUT_MINUTES * 60
    for key in _throttle_keys(request, identifier):
        cache.set(key, cache.get(key, 0) + 1, timeout)


def _clear_failures(request, identifier):
    cache.delete(_throttle_keys(request, identifier)[0])


# ==========================================================================
#  2. Landing / register / login / logout
# ==========================================================================
def landing_view(request):
    if request.user.is_authenticated:
        return redirect(_home_for(request.user))
    return render(request, 'landing.html')


def register_view(request):
    """New students only. Everybody who registers here is a STUDENT (owners are
    created with:  python manage.py create_owner)."""
    if request.user.is_authenticated:
        return redirect(_home_for(request.user))

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        try:
            # role defaults to student; the readable password copy is stored for the admin
            user = create_account(cd['username'], cd['full_name'], cd['phone'], cd['password'])
        except IntegrityError:                                # two people registered the same phone/username at once
            form.add_error(None, 'That username or phone number was just taken. Please try again.')
        else:
            login(request, user)
            messages.success(request, f'Welcome, {user.first_name}! Your account is ready.')
            return redirect('practice')
    return render(request, 'register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_home_for(request.user))

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        identifier = form.cleaned_data['identifier']
        password = form.cleaned_data['password']
        if _is_locked(request, identifier):
            form.add_error(None, f'Too many wrong attempts. Please wait {settings.LOGIN_LOCKOUT_MINUTES} minutes, '
                                 f'or contact the admin.')
        else:
            found = find_user_by_identifier(identifier)
            user = authenticate(request, username=found.username, password=password) if found else None
            if user is not None:
                _clear_failures(request, identifier)
                login(request, user)
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
                    return redirect(next_url)
                return redirect(_home_for(user))
            _record_failure(request, identifier)
            form.add_error(None, 'Wrong phone number or password. Please try again.')
    return render(request, 'login.html', {'form': form, 'next': request.GET.get('next', '')})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('landing')


# ==========================================================================
#  3. Practice home, dashboard, lists
# ==========================================================================
@login_required
def practice_view(request):
    """Home after login: your stats + the three practice categories."""
    rank, participants = stats.today_rank(request.user)
    today = timezone.localdate()
    context = {
        'streak': stats.current_streak(request.user),
        'top_score': stats.top_score(request.user),
        'today_rank': rank,
        'today_participants': participants,
        'count_progressive': Assignment.objects.filter(category=Assignment.CATEGORY_PROGRESSIVE).count(),
        'count_kailashchand': Assignment.objects.filter(category=Assignment.CATEGORY_KAILASHCHAND).count(),
        # Short Dictation also holds the old "daily" assignments
        'count_short': Assignment.objects.filter(
            category__in=[Assignment.CATEGORY_SHORT, Assignment.CATEGORY_DAILY]).count(),
        # small banner if the owner uploaded a daily assignment today
        'todays_daily': Assignment.objects.filter(category=Assignment.CATEGORY_DAILY, date=today).first(),
    }
    return render(request, 'student/practice.html', context)


@login_required
def student_dashboard(request):
    mine = Submission.objects.filter(student=request.user)
    summary = mine.aggregate(
        attempts=Count('id'), avg_accuracy=Avg('accuracy'), best=Max('accuracy'),
        total_time=Sum('time_taken'), avg_wpm=Avg('wpm_used'),
    )
    # last 20 attempts, oldest first, for the accuracy trend chart
    trend = [s.accuracy for s in reversed(list(mine.order_by('-submitted_at')[:20]))]
    page = _paginate(request, mine.select_related('assignment'), 15)
    context = {
        'attempts': summary['attempts'],
        'avg_accuracy': summary['avg_accuracy'] or 0,
        'best_accuracy': summary['best'] or 0,
        'total_minutes': round((summary['total_time'] or 0) / 60),
        'streak': stats.current_streak(request.user),
        'trend': trend,
        'page': page,
    }
    return render(request, 'student/dashboard.html', context)


def _assignment_list(request, categories, template):
    """Shared by the three list pages. Adds 'attempts' and 'best' (this student's own)."""
    mine = Q(submissions__student=request.user)
    queryset = (
        Assignment.objects.filter(category__in=categories)
        .annotate(attempts=Count('submissions', filter=mine, distinct=True),
                  best=Max('submissions__accuracy', filter=mine))
        .order_by('-date', '-id')
    )
    page = _paginate(request, queryset, 12)
    return render(request, template, {'page': page, 'assignments': page.object_list})


@login_required
def progressive_view(request):
    return _assignment_list(request, [Assignment.CATEGORY_PROGRESSIVE], 'student/progressive.html')


@login_required
def kailashchand_view(request):
    return _assignment_list(request, [Assignment.CATEGORY_KAILASHCHAND], 'student/kailashchand.html')


@login_required
def short_dictation_view(request):
    # Short dictation + every "daily" assignment (old and new)
    return _assignment_list(request, [Assignment.CATEGORY_SHORT, Assignment.CATEGORY_DAILY],
                            'student/short_dictation.html')


# ==========================================================================
#  4. The 3-phase assignment flow
# ==========================================================================
@login_required
def assignment_listen(request, pk):
    """Phase 1 - listen. Opening this page always starts a FRESH attempt."""
    assignment = get_object_or_404(Assignment, pk=pk)
    request.session.pop(_typing_key(pk), None)
    return render(request, 'student/assignment_listen.html', {
        'assignment': assignment,
        'audio_url': assignment.audio_file.url if assignment.audio_file else '',
        'wpm_min': settings.WPM_MIN,
        'wpm_max': settings.WPM_MAX,
        'redirect_seconds': settings.AUDIO_END_REDIRECT_SECONDS,
    })


@login_required
def assignment_reading(request, pk):
    """Phase 2 - 5 minutes to read your own shorthand notes."""
    assignment = get_object_or_404(Assignment, pk=pk)
    return render(request, 'student/assignment_reading.html', {
        'assignment': assignment,
        'reading_seconds': settings.READING_SECONDS,
    })


@login_required
def assignment_typing(request, pk):
    """Phase 3 - typing. The start time is kept on the SERVER (in the session) so
    refreshing the page does not give extra time."""
    assignment = get_object_or_404(Assignment, pk=pk)
    total = settings.TYPING_SECONDS
    now = time.time()
    start = request.session.get(_typing_key(pk))
    # no start yet, or an old abandoned attempt (more than 10 minutes past its end) -> start fresh
    if start is None or now - start > total + 600:
        start = now
        request.session[_typing_key(pk)] = start
    remaining = max(0, int(total - (now - start)))
    return render(request, 'student/assignment_typing.html', {
        'assignment': assignment,
        'remaining_seconds': remaining,
        'total_seconds': total,
        'attempt_id': int(start),                 # lets the browser tell old drafts from this attempt
    })


def _update_weak_words(user, diff):
    """Add this attempt's mistyped words to the student's weak-word list."""
    now = timezone.now()
    for word, n in Counter(weak_word_candidates(diff)).items():
        word = word[:100]
        obj, created = WeakWord.objects.get_or_create(
            student=user, word=word, defaults={'miss_count': n, 'last_seen': now})
        if not created:
            WeakWord.objects.filter(pk=obj.pk).update(miss_count=F('miss_count') + n, last_seen=now)


@login_required
@require_POST
def submit_assignment(request, pk):
    """Check the typed text and save the result."""
    assignment = get_object_or_404(Assignment, pk=pk)
    typed = request.POST.get('typed_text', '')[:80000]      # safety cap on size
    wpm_used = _clamp(request.POST.get('wpm_used'), 30, 250, settings.DEFAULT_BASE_WPM)

    # time taken: trust the server's clock; fall back to what the browser sent
    total = settings.TYPING_SECONDS
    start = request.session.pop(_typing_key(pk), None)
    if start:
        time_taken = int(min(total, max(0, time.time() - start)))
    else:
        time_taken = _clamp(request.POST.get('client_seconds'), 0, total, 0)

    result = compare_texts(assignment.paragraph_text, typed)     # <-- the marking engine
    with transaction.atomic():
        submission = Submission.objects.create(
            student=request.user, assignment=assignment, typed_text=typed,
            mistake_count=result['mistakes'],
            wrong_count=result['wrong'], missing_count=result['missing'], extra_count=result['extra'],
            spelling_count=result['spelling'], capital_count=result['capital'], punct_count=result['punct'],
            total_words=result['total_words'], typed_words=result['typed_words'],
            error_pct=result['error_pct'], accuracy=result['accuracy'],
            wpm_used=wpm_used, time_taken=time_taken, diff_data=result['diff'],
        )
        _update_weak_words(request.user, result['diff'])
    return redirect('result', pk=submission.pk)


def result_context(submission):
    """Everything the result template needs (also used by the owner's detail page)."""
    assignment = submission.assignment
    return {
        'sub': submission,
        'student': submission.student,
        'assignment': assignment,
        'diff': submission.diff_data,
        # (limit, within_limit) pairs for the "Within the 5% limit" badges
        'limits': [(limit, submission.error_pct <= limit) for limit in ERROR_LIMITS],
        'strokes_url': assignment.strokes_pdf.url if assignment.strokes_pdf else '',
    }


@login_required
def result_view(request, pk):
    submission = get_object_or_404(Submission.objects.select_related('assignment'), pk=pk, student=request.user)
    return render(request, 'student/result.html', result_context(submission))


# ==========================================================================
#  5. Weak words
# ==========================================================================
@login_required
def weak_words_view(request):
    words = WeakWord.objects.filter(student=request.user)       # already ordered: most missed first
    page = _paginate(request, words, 40)
    return render(request, 'student/weak_words.html', {
        'page': page,
        'weak_words': page.object_list,
        'total_words': words.count(),
        'total_misses': words.aggregate(n=Sum('miss_count'))['n'] or 0,
        'offset': (page.number - 1) * 40,
    })


# ==========================================================================
#  6. Profile
# ==========================================================================
def _render_profile(request, profile_form=None, password_form=None):
    user = request.user
    profile = user.profile
    if profile_form is None:
        profile_form = ProfileForm(user=user, initial={
            'full_name': user.first_name, 'username': user.username, 'phone': profile.phone or ''})
    return render(request, 'student/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form or PasswordForm(user=user),
        'attempts': Submission.objects.filter(student=user).count(),
        'profile': profile,
    })


@login_required
def profile_view(request):
    return _render_profile(request)


@login_required
@require_POST
def update_profile(request):
    form = ProfileForm(request.POST, user=request.user)
    if form.is_valid():
        cd = form.cleaned_data
        user = request.user
        try:
            with transaction.atomic():
                user.first_name = cd['full_name']
                user.username = cd['username']
                user.save()
                user.profile.phone = cd['phone']
                user.profile.save(update_fields=['phone'])
        except IntegrityError:
            form.add_error(None, 'That username or phone number is already used by someone else.')
        else:
            messages.success(request, 'Profile updated.')
            return redirect('profile')
    return _render_profile(request, profile_form=form)


@login_required
@require_POST
def change_password(request):
    form = PasswordForm(request.POST, user=request.user)
    if form.is_valid():
        set_password(request.user, form.cleaned_data['new_password'])   # updates BOTH copies
        update_session_auth_hash(request, request.user)                 # keeps you logged in
        messages.success(request, 'Password changed.')
        return redirect('profile')
    return _render_profile(request, password_form=form)
