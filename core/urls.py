"""
core/urls.py - every page of the site.
Format:  path('address/', view_function, name='name_used_in_templates')
"""
from django.urls import path, re_path

from . import media, owner_views, views

urlpatterns = [
    # ---- public ----
    path('', views.landing_view, name='landing'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),                 # POST only

    # ---- student: home + lists ----
    path('practice/', views.practice_view, name='practice'),
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('progressive/', views.progressive_view, name='progressive'),
    path('kailashchand/', views.kailashchand_view, name='kailashchand'),
    path('short-dictation/', views.short_dictation_view, name='short_dictation'),
    path('weak-words/', views.weak_words_view, name='weak_words'),

    # ---- student: the 3-phase assignment flow ----
    path('assignment/<int:pk>/', views.assignment_listen, name='assignment'),                  # 1. listen
    path('assignment/<int:pk>/reading/', views.assignment_reading, name='assignment_reading'), # 2. read
    path('assignment/<int:pk>/typing/', views.assignment_typing, name='assignment_typing'),    # 3. type
    path('assignment/<int:pk>/submit/', views.submit_assignment, name='submit_assignment'),    #    submit
    path('result/<int:pk>/', views.result_view, name='result'),

    # ---- student: profile ----
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/password/', views.change_password, name='change_password'),

    # ---- owner / admin ----
    path('owner/', owner_views.owner_dashboard, name='owner_dashboard'),
    path('owner/upload/', owner_views.upload_assignment, name='upload_assignment'),
    path('owner/assignment/<int:pk>/edit/', owner_views.edit_assignment, name='edit_assignment'),
    path('owner/assignment/<int:pk>/delete/', owner_views.delete_assignment, name='delete_assignment'),
    path('owner/students/', owner_views.owner_students, name='owner_students'),
    path('owner/submission/<int:pk>/', owner_views.view_submission, name='view_submission'),

    # ---- uploaded audio / PDFs (login required, supports audio seeking) ----
    re_path(r'^media/(?P<path>.+)$', media.serve_media, name='media'),
]
