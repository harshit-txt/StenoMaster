"""
core/owner_views.py - pages for the OWNER / ADMIN only.

    owner_dashboard     overview + recent submissions + all assignments
    upload_assignment   add a new dictation
    edit_assignment     change an existing one
    delete_assignment   remove one (and its submissions)
    owner_students      every student, with search by name / phone and their PASSWORD
    view_submission     full result of any student's attempt
"""
import re
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .accounts import is_owner
from .forms import AssignmentForm
from .models import Assignment, Submission, UserProfile
from .views import result_context


def owner_required(view):
    """Only the owner may open the page. Everyone else is sent back to Practice."""
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_owner(request.user):
            raise PermissionDenied          # shows templates/403.html
        return view(request, *args, **kwargs)
    return wrapper


@owner_required
def owner_dashboard(request):
    today = timezone.localdate()
    students = UserProfile.objects.filter(role=UserProfile.ROLE_STUDENT)
    context = {
        'student_count': students.count(),
        'assignment_count': Assignment.objects.count(),
        'submission_count': Submission.objects.count(),
        'today_count': Submission.objects.filter(submitted_at__date=today).count(),
        'recent': Submission.objects.select_related('student', 'student__profile', 'assignment')[:10],
    }
    page = Paginator(Assignment.objects.annotate(attempts=Count('submissions')).order_by('-date', '-id'), 10).get_page(request.GET.get('page'))
    context.update({'page': page, 'assignments': page.object_list})
    return render(request, 'owner/dashboard.html', context)


@owner_required
def upload_assignment(request):
    form = AssignmentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        assignment = form.save(commit=False)
        assignment.created_by = request.user
        assignment.save()
        messages.success(request, f'Uploaded "{assignment.display_title}" - {assignment.word_count} words.')
        return redirect('owner_dashboard')
    return render(request, 'owner/upload.html', {'form': form, 'editing': None})


@owner_required
def edit_assignment(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    old_audio, old_pdf = assignment.audio_file.name, assignment.strokes_pdf.name
    form = AssignmentForm(request.POST or None, request.FILES or None, instance=assignment)
    if request.method == 'POST' and form.is_valid():
        remove_pdf = form.cleaned_data['remove_strokes'] and not request.FILES.get('strokes_pdf')
        assignment = form.save(commit=False)
        if remove_pdf:
            assignment.strokes_pdf = ''
        assignment.save()
        # delete the replaced files so the disk does not fill up with old copies
        if old_audio and assignment.audio_file.name != old_audio:
            assignment.audio_file.storage.delete(old_audio)
        if old_pdf and assignment.strokes_pdf.name != old_pdf:
            assignment.strokes_pdf.storage.delete(old_pdf)
        messages.success(request, f'Saved changes to "{assignment.display_title}".')
        return redirect('owner_dashboard')
    return render(request, 'owner/upload.html', {'form': form, 'editing': assignment})


@owner_required
@require_POST
def delete_assignment(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    title = assignment.display_title
    assignment.delete()           # also deletes its submissions and files
    messages.success(request, f'Deleted "{title}".')
    return redirect('owner_dashboard')


@owner_required
def owner_students(request):
    """All students + their passwords. Search by name, username or phone number.
    Several words narrow the result: "rahul 43210" = name has rahul AND phone has 43210."""
    q = request.GET.get('q', '').strip()
    profiles = (
        UserProfile.objects.filter(role=UserProfile.ROLE_STUDENT)
        .select_related('user')
        .annotate(attempts=Count('user__submissions', distinct=True),
                  best=Max('user__submissions__accuracy'),
                  last_active=Max('user__submissions__submitted_at'))
        .order_by('user__first_name', 'user__username')
    )
    total = profiles.count()
    for word in q.split():
        condition = Q(user__first_name__icontains=word) | Q(user__username__icontains=word)
        digits = re.sub(r'\D', '', word)
        if digits:
            condition |= Q(phone__contains=digits[-10:])
        profiles = profiles.filter(condition)
    page = Paginator(profiles, 25).get_page(request.GET.get('page'))
    return render(request, 'owner/students.html', {'page': page, 'q': q, 'total': page.paginator.count if q else total})


@owner_required
def view_submission(request, pk):
    submission = get_object_or_404(Submission.objects.select_related('assignment', 'student', 'student__profile'), pk=pk)
    return render(request, 'owner/submission_detail.html', result_context(submission))
