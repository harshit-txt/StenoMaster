"""
core/forms.py - all forms (validation lives here).

RegisterForm    new student: name, username, phone, password
LoginForm       phone (or username) + password
ProfileForm     student edits own name / username / phone
PasswordForm    student changes own password
AssignmentForm  owner uploads / edits a dictation
"""
import os

from django import forms
from django.conf import settings
from django.contrib.auth.models import User

from .accounts import USERNAME_RE, normalize_phone
from .models import Assignment, UserProfile

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.oga', '.m4a', '.aac', '.opus', '.webm'}


def _check_password_length(password):
    if len(password) < settings.MIN_PASSWORD_LENGTH:
        raise forms.ValidationError(f'Password must be at least {settings.MIN_PASSWORD_LENGTH} characters.')
    return password


class StyledFormMixin:
    """Gives every widget the CSS class the stylesheet expects ("input" / "file-input"),
    so all forms look the same. To restyle forms, edit .input in static/css/style.css."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            css = 'file-input' if isinstance(widget, forms.FileInput) else 'input'
            widget.attrs['class'] = f"{widget.attrs.get('class', '')} {css}".strip()


class _AccountFieldsMixin:
    """Shared clean_ methods for name / username / phone. Subclasses set self.user
    (the account being edited, or None for a new account) so it can ignore itself
    in the "already taken" checks."""
    user = None

    def clean_full_name(self):
        name = ' '.join(self.cleaned_data['full_name'].split())
        if len(name) < 2:
            raise forms.ValidationError('Please enter your full name.')
        return name

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if not USERNAME_RE.match(username):
            raise forms.ValidationError('Username must be 3-30 characters: letters, numbers, underscore or dot only.')
        taken = User.objects.filter(username__iexact=username)
        if self.user is not None:
            taken = taken.exclude(pk=self.user.pk)
        if taken.exists():
            raise forms.ValidationError('This username is already taken. Please choose another.')
        return username

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data['phone'])
        if not phone:
            raise forms.ValidationError('Enter a valid 10-digit mobile number.')
        taken = UserProfile.objects.filter(phone=phone)
        if self.user is not None:
            taken = taken.exclude(user=self.user)
        if taken.exists():
            raise forms.ValidationError('This phone number is already registered. Please log in, or contact the admin.')
        return phone


class RegisterForm(StyledFormMixin, _AccountFieldsMixin, forms.Form):
    # EDIT the labels / hints here
    full_name = forms.CharField(label='Full name', max_length=60,
                                widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    username = forms.CharField(label='Username', max_length=30, help_text='Letters, numbers, underscore or dot.',
                               widget=forms.TextInput(attrs={'autocomplete': 'username', 'autocapitalize': 'none'}))
    phone = forms.CharField(label='Phone number', max_length=20,
                            widget=forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel', 'autocomplete': 'tel-national',
                                                          'placeholder': '98765 43210'}))
    password = forms.CharField(label='Password', max_length=128, help_text='At least 6 characters.',
                               widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    confirm_password = forms.CharField(label='Confirm password', max_length=128,
                                       widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def clean_password(self):
        return _check_password_length(self.cleaned_data['password'])

    def clean(self):
        data = super().clean()
        if data.get('password') and data.get('confirm_password') and data['password'] != data['confirm_password']:
            self.add_error('confirm_password', 'The two passwords do not match.')
        return data


class LoginForm(StyledFormMixin, forms.Form):
    # one box that accepts the phone number (students) or the username (the admin can use either)
    identifier = forms.CharField(label='Phone number', max_length=60,
                                 widget=forms.TextInput(attrs={'autocomplete': 'username', 'autocapitalize': 'none',
                                                               'placeholder': '98765 43210', 'autofocus': True}))
    password = forms.CharField(label='Password', max_length=128,
                               widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))


class ProfileForm(StyledFormMixin, _AccountFieldsMixin, forms.Form):
    full_name = forms.CharField(label='Full name', max_length=60)
    username = forms.CharField(label='Username', max_length=30)
    phone = forms.CharField(label='Phone number', max_length=20,
                            widget=forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel'}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user


class PasswordForm(StyledFormMixin, forms.Form):
    current_password = forms.CharField(label='Current password', max_length=128,
                                       widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))
    new_password = forms.CharField(label='New password', max_length=128, help_text='At least 6 characters.',
                                   widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    confirm_password = forms.CharField(label='Confirm new password', max_length=128,
                                       widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        if not self.user.check_password(self.cleaned_data['current_password']):
            raise forms.ValidationError('Your current password is not correct.')
        return self.cleaned_data['current_password']

    def clean_new_password(self):
        return _check_password_length(self.cleaned_data['new_password'])

    def clean(self):
        data = super().clean()
        if data.get('new_password') and data.get('confirm_password') and data['new_password'] != data['confirm_password']:
            self.add_error('confirm_password', 'The two passwords do not match.')
        return data


class AssignmentForm(StyledFormMixin, forms.ModelForm):
    """Owner upload / edit form. Word count is worked out automatically."""

    # edit page only: tick to delete the current strokes PDF
    remove_strokes = forms.BooleanField(required=False, label='Remove the current strokes PDF')

    class Meta:
        model = Assignment
        fields = ['title', 'category', 'date', 'paragraph_text', 'audio_file', 'base_wpm', 'strokes_pdf']
        labels = {
            'paragraph_text': 'Dictation paragraph',
            'audio_file': 'Audio file',
            'strokes_pdf': 'Strokes PDF (optional)',
            'base_wpm': 'Speed the audio was recorded at (WPM)',
        }
        help_texts = {
            'base_wpm': 'The real speed of your recording. The student\'s speed slider starts here (60-120 WPM); moving it makes the audio play faster or slower than this.',
            'strokes_pdf': 'Shown to the student on the result page after they submit.',
        }
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'paragraph_text': forms.Textarea(attrs={'rows': 14}),
            'audio_file': forms.FileInput(attrs={'accept': 'audio/*'}),
            'strokes_pdf': forms.FileInput(attrs={'accept': 'application/pdf,.pdf'}),
        }

    def clean_paragraph_text(self):
        text = self.cleaned_data['paragraph_text'].strip()
        if not text:
            raise forms.ValidationError('Paste the dictation paragraph.')
        return text

    def clean_base_wpm(self):
        wpm = self.cleaned_data['base_wpm']
        if not 30 <= wpm <= 250:
            raise forms.ValidationError('Enter the speed the audio was recorded at (30-250 words per minute).')
        return wpm

    def clean_audio_file(self):
        f = self.cleaned_data.get('audio_file')
        if f and hasattr(f, 'size'):          # a new file was chosen
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in AUDIO_EXTENSIONS:
                raise forms.ValidationError('Upload an audio file (MP3 recommended; WAV, OGG, M4A also work).')
            if f.size > settings.MAX_AUDIO_MB * 1024 * 1024:
                raise forms.ValidationError(f'Audio is too big (max {settings.MAX_AUDIO_MB} MB).')
        return f

    def clean_strokes_pdf(self):
        f = self.cleaned_data.get('strokes_pdf')
        if f and hasattr(f, 'size'):
            if os.path.splitext(f.name)[1].lower() != '.pdf':
                raise forms.ValidationError('The strokes file must be a PDF.')
            if f.size > settings.MAX_PDF_MB * 1024 * 1024:
                raise forms.ValidationError(f'PDF is too big (max {settings.MAX_PDF_MB} MB).')
            head = f.read(5)
            f.seek(0)
            if head != b'%PDF-':
                raise forms.ValidationError('This file does not look like a real PDF.')
        return f

    def clean(self):
        data = super().clean()
        # A new dictation needs audio. When editing, keeping the old audio is fine.
        has_old = bool(self.instance and self.instance.pk and self.instance.audio_file)
        if not data.get('audio_file') and not has_old and 'audio_file' not in self.errors:
            self.add_error('audio_file', 'This field is required: upload the dictation audio.')
        return data
