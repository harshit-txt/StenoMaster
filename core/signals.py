"""Signals: keep profiles and uploaded files tidy."""
from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Assignment, UserProfile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Every new login automatically gets a UserProfile.
    Superusers (created with createsuperuser) become owners, everybody else a student."""
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={'role': UserProfile.ROLE_OWNER if instance.is_superuser else UserProfile.ROLE_STUDENT},
        )


@receiver(post_delete, sender=Assignment)
def delete_assignment_files(sender, instance, **kwargs):
    """Remove the audio / PDF from disk when an assignment is deleted."""
    for f in (instance.audio_file, instance.strokes_pdf):
        if f:
            f.delete(save=False)
