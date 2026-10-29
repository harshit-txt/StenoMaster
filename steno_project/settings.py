"""
StenoMaster - Django settings.

Search for "EDIT" to find the values you are most likely to change.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
#  Core
# --------------------------------------------------------------------------
# EDIT: before putting the site on the internet set DJANGO_SECRET_KEY (environment
# variable) and DJANGO_DEBUG=0.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-only-secret-key-change-me-before-deploying')
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]

# Render (render.com) tells us the site's address in this variable - allow it automatically.
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
    CSRF_TRUSTED_ORIGINS.append(f'https://{_render_host}')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',            # our app
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',      # serves CSS/JS when DEBUG is off (online)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# The strokes PDF is shown in an <iframe> on the result page, so allow same-site framing.
X_FRAME_OPTIONS = 'SAMEORIGIN'

ROOT_URLCONF = 'steno_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.site',     # admin phone, is_owner, site name
            ],
        },
    },
]

WSGI_APPLICATION = 'steno_project.wsgi.application'
ASGI_APPLICATION = 'steno_project.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Students pick their own simple passwords and the admin can look them up, so we
# do not force Django's strict password rules. Our own forms require 6+ characters
# (see MIN_PASSWORD_LENGTH below).
AUTH_PASSWORD_VALIDATORS = []

# Makes "python manage.py test" much faster (a quick hasher is used ONLY while testing).
import sys  # noqa: E402
if 'test' in sys.argv:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# --------------------------------------------------------------------------
#  Language / time
# --------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
#  Static + uploaded files
# --------------------------------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'          # audio + strokes PDFs are saved here (a single path, not a list)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --------------------------------------------------------------------------
#  Login
# --------------------------------------------------------------------------
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'practice'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14          # stay logged in for 14 days

# Too many wrong passwords in a row locks that phone/IP for a while.
LOGIN_MAX_ATTEMPTS = 8                # EDIT: wrong attempts allowed ...
LOGIN_LOCKOUT_MINUTES = 10            # EDIT: ... before waiting this many minutes

MIN_PASSWORD_LENGTH = 6               # EDIT: shortest password allowed at register / change

# --------------------------------------------------------------------------
#  Site texts shown to everyone                                       EDIT
# --------------------------------------------------------------------------
SITE_NAME = 'StenoMaster'
ADMIN_CONTACT_PHONE = '92118 94802'   # shown in the footer on every page
ADMIN_CONTACT_MESSAGE = 'Contact if you forgot your password or have any issues.'

# --------------------------------------------------------------------------
#  Practice flow timings                                              EDIT
# --------------------------------------------------------------------------
READING_SECONDS = 5 * 60              # phase 2: reading time
TYPING_SECONDS = 50 * 60              # phase 3: typing time (auto-submits at 0)
AUDIO_END_REDIRECT_SECONDS = 5        # wait after the audio ends, then go to reading
WPM_MIN = 60                          # dictation speed slider range
WPM_MAX = 120
DEFAULT_BASE_WPM = 80                 # speed the owner's recording is made at

# --------------------------------------------------------------------------
#  Upload limits                                                      EDIT
# --------------------------------------------------------------------------
MAX_AUDIO_MB = 60
MAX_PDF_MB = 15
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# --------------------------------------------------------------------------
#  Extra security when DEBUG is off (production)
# --------------------------------------------------------------------------
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get('DJANGO_SSL_REDIRECT', '1') == '1'
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
