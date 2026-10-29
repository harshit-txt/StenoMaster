"""Small statistics helpers used by the practice page and dashboard."""
from datetime import timedelta

from django.db.models import Max
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import Submission


def current_streak(user):
    """Number of days in a row (ending today, or yesterday if you have not practised
    yet today) on which the student submitted at least one assignment."""
    days = set(
        Submission.objects.filter(student=user)
        .annotate(d=TruncDate('submitted_at'))
        .values_list('d', flat=True)
        .distinct()
    )
    day = timezone.localdate()
    if day not in days:
        day -= timedelta(days=1)          # today does not break the streak until it is over
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def today_rank(user):
    """(rank, participants) among students who practised today, by best accuracy.
    rank is None if this user has not submitted anything today."""
    today = timezone.localdate()
    rows = (
        Submission.objects.filter(submitted_at__date=today, student__profile__role='student')
        .values('student')
        .annotate(best=Max('accuracy'))
    )
    bests = {r['student']: r['best'] for r in rows}
    mine = bests.get(user.id)
    if mine is None:
        return None, len(bests)
    return 1 + sum(1 for v in bests.values() if v > mine), len(bests)


def top_score(user):
    best = Submission.objects.filter(student=user).aggregate(m=Max('accuracy'))['m']
    return round(best or 0, 1)
