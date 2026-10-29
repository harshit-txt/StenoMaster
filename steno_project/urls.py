"""Root URL configuration. All site pages live in core/urls.py."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),     # Django's built-in admin (superuser only)
    path('', include('core.urls')),      # the whole StenoMaster site (also serves /media/)
]
