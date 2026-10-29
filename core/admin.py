"""Django's built-in admin (/admin/) - handy for fixing data by hand.
The day-to-day admin screens for the owner are the "Owner" pages of the site itself."""
from django.contrib import admin

from .models import Assignment, Submission, UserProfile, WeakWord


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'plain_password', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__first_name', 'phone')


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('display_title', 'category', 'date', 'word_count', 'base_wpm')
    list_filter = ('category',)
    search_fields = ('title', 'paragraph_text')


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'accuracy', 'mistake_count', 'submitted_at')
    list_filter = ('assignment__category',)
    search_fields = ('student__username', 'student__first_name')


@admin.register(WeakWord)
class WeakWordAdmin(admin.ModelAdmin):
    list_display = ('student', 'word', 'miss_count', 'last_seen')
    search_fields = ('word', 'student__username')
