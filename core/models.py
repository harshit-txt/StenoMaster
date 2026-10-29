"""
core/models.py - database tables.

    UserProfile  extra info for each login (role, phone, password the admin can see)
    Assignment   one dictation (paragraph + audio + optional strokes PDF)
    Submission   one attempt by a student, with the full word-by-word result
    WeakWord     words a student keeps typing wrong
"""
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_STUDENT = 'student'
    ROLE_CHOICES = [(ROLE_OWNER, 'Owner / Admin'), (ROLE_STUDENT, 'Student')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_STUDENT)

    # 10-digit mobile number, digits only (e.g. "9211894802"). Students log in with it.
    # null=True so several accounts without a phone (e.g. a superuser) can exist.
    phone = models.CharField(max_length=10, unique=True, null=True, blank=True)

    # The password exactly as the student typed it, so the admin can tell it to a
    # student who forgot it. Django still keeps the normal hashed password for the
    # actual login check - this copy is ONLY for the admin "Students" page.
    # Always change passwords through core.accounts.set_password() so both stay in sync.
    plain_password = models.CharField(max_length=128, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.role})'

    @property
    def is_owner(self):
        return self.role == self.ROLE_OWNER


class Assignment(models.Model):
    CATEGORY_DAILY = 'daily'
    CATEGORY_PROGRESSIVE = 'progressive'
    CATEGORY_KAILASHCHAND = 'kailashchand'
    CATEGORY_SHORT = 'short_dictation'
    CATEGORY_CHOICES = [
        (CATEGORY_DAILY, 'Daily'),
        (CATEGORY_PROGRESSIVE, 'Progressive'),
        (CATEGORY_KAILASHCHAND, 'Kailashchandra'),
        (CATEGORY_SHORT, 'Short Dictation'),
    ]

    title = models.CharField(max_length=150, blank=True, help_text='Optional. Shown in the lists.')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_DAILY)
    date = models.DateField(default=timezone.localdate)
    paragraph_text = models.TextField()
    audio_file = models.FileField(upload_to='audio/%Y/%m/', blank=True)
    strokes_pdf = models.FileField(upload_to='strokes/%Y/%m/', blank=True)
    word_count = models.PositiveIntegerField(default=0, editable=False)   # filled in automatically
    # Speed (words per minute) the audio was RECORDED at. The listening page speeds the
    # audio up/down relative to this number.
    base_wpm = models.PositiveSmallIntegerField(default=settings.DEFAULT_BASE_WPM)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='uploaded_assignments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def save(self, *args, **kwargs):
        self.word_count = len(self.paragraph_text.split())
        super().save(*args, **kwargs)

    @property
    def display_title(self):
        return self.title or f'{self.get_category_display()} - {self.date:%d %b %Y}'

    def __str__(self):
        return self.display_title


class Submission(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    typed_text = models.TextField(blank=True)

    # --- result (filled in by core.checker.compare_texts) ---
    mistake_count = models.FloatField(default=0)                   # total, halves allowed (e.g. 12.5)
    wrong_count = models.PositiveIntegerField(default=0)           # wrong word typed          (full)
    missing_count = models.PositiveIntegerField(default=0)         # word left out             (full)
    extra_count = models.PositiveIntegerField(default=0)           # word added / repeated     (full)
    spelling_count = models.PositiveIntegerField(default=0)        # spelling + singular/plural (half)
    capital_count = models.PositiveIntegerField(default=0)         # missing capital letter     (half)
    punct_count = models.PositiveIntegerField(default=0)           # full stop missing/misplaced (half)
    total_words = models.PositiveIntegerField(default=0)           # words in the original passage
    typed_words = models.PositiveIntegerField(default=0)
    error_pct = models.FloatField(default=0)                       # mistakes / total_words * 100
    accuracy = models.FloatField(default=0)                        # 100 - error_pct

    wpm_used = models.PositiveSmallIntegerField(default=settings.DEFAULT_BASE_WPM)
    time_taken = models.PositiveIntegerField(default=0)            # seconds spent typing
    submitted_at = models.DateTimeField(auto_now_add=True)
    diff_data = models.JSONField(default=list, blank=True)         # word-by-word result for the result page

    class Meta:
        ordering = ['-submitted_at']
        indexes = [models.Index(fields=['student', '-submitted_at'])]

    def __str__(self):
        return f'{self.student.username} - {self.assignment_id} - {self.accuracy}%'


class WeakWord(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='weak_words')
    word = models.CharField(max_length=100)
    miss_count = models.PositiveIntegerField(default=0)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-miss_count', 'word']
        constraints = [models.UniqueConstraint(fields=['student', 'word'], name='unique_weak_word_per_student')]

    def __str__(self):
        return f'{self.word} x{self.miss_count}'
