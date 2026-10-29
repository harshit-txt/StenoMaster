"""
core/accounts.py - helpers for phone numbers, passwords and "who is the owner".
"""
import re

from django.contrib.auth.models import User
from django.db import transaction

from .models import UserProfile

USERNAME_RE = re.compile(r'^[A-Za-z0-9_.]{3,30}$')


def normalize_phone(raw):
    """'92118 94802', '+91 92118-94802', '09211894802'  ->  '9211894802'.
    Returns None if it is not a valid 10-digit Indian mobile number."""
    digits = re.sub(r'\D', '', raw or '')
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]
    if re.fullmatch(r'[6-9]\d{9}', digits):
        return digits
    return None


def format_phone(digits):
    """'9211894802' -> '92118 94802' (the way it is displayed)."""
    digits = digits or ''
    return f'{digits[:5]} {digits[5:]}'.strip()


def is_owner(user):
    """True for the admin/owner: role 'owner' or a Django superuser."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.is_owner)


def set_password(user, raw_password):
    """Change a password the right way: the normal hashed password (for login) AND the
    copy the admin can read. Always use this instead of user.set_password()."""
    user.set_password(raw_password)
    user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.plain_password = raw_password
    profile.save(update_fields=['plain_password'])


def find_user_by_identifier(identifier):
    """Login box accepts a phone number or a username. Returns a User or None."""
    identifier = (identifier or '').strip()
    if not identifier:
        return None
    phone = normalize_phone(identifier)
    if phone:
        profile = UserProfile.objects.select_related('user').filter(phone=phone).first()
        if profile:
            return profile.user
    return User.objects.filter(username__iexact=identifier).first()


@transaction.atomic
def create_account(username, full_name, phone, password, role=UserProfile.ROLE_STUDENT, superuser=False):
    """The one place accounts are created (register page, create_owner command, tests).
    Stores the hashed password for login AND the readable copy for the admin."""
    user = User(username=username, first_name=full_name, is_staff=superuser, is_superuser=superuser)
    user.set_password(password)
    user.save()                              # signal creates the profile
    profile = user.profile
    profile.role = role
    profile.phone = phone
    profile.plain_password = password
    profile.save()
    return user
