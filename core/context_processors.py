"""Variables available in EVERY template (see TEMPLATES in settings.py)."""
import re

from django.conf import settings

from .accounts import is_owner


def site(request):
    digits = re.sub(r'\D', '', settings.ADMIN_CONTACT_PHONE)[-10:]
    return {
        'SITE_NAME': settings.SITE_NAME,
        'ADMIN_PHONE': settings.ADMIN_CONTACT_PHONE,            # shown on the page: "92118 94802"
        'ADMIN_PHONE_TEL': '+91' + digits,                      # used in the tel: link
        'ADMIN_CONTACT_MESSAGE': settings.ADMIN_CONTACT_MESSAGE,
        'is_owner': is_owner(request.user),                     # True for the admin
    }
