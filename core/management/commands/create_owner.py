"""
Create the owner / admin account.

    python manage.py create_owner

Asks for a name, username, phone number and password. The owner can then log in
with the phone number (or username) and sees the Owner pages (upload, students list ...).
You can also pass everything on the command line:

    python manage.py create_owner --name "Admin" --username admin --phone 9211894802 --password secret123
"""
from getpass import getpass

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.accounts import USERNAME_RE, create_account, normalize_phone
from core.models import UserProfile


class Command(BaseCommand):
    help = 'Create the owner/admin account (logs in with phone number or username).'

    def add_arguments(self, parser):
        parser.add_argument('--name')
        parser.add_argument('--username')
        parser.add_argument('--phone')
        parser.add_argument('--password')
        parser.add_argument('--if-missing', action='store_true',
                            help='do nothing (no error) if this username already exists - used by build.sh')

    def handle(self, *args, **opts):
        if opts['if_missing'] and opts['username'] and User.objects.filter(username__iexact=opts['username']).exists():
            self.stdout.write('Owner already exists - skipped.')
            return
        name = opts['name'] or input('Full name: ').strip()
        username = opts['username'] or input('Username: ').strip()
        phone_raw = opts['phone'] or input('Phone number (10 digits): ').strip()
        password = opts['password'] or getpass('Password: ')
        if not opts['password'] and password != getpass('Password (again): '):
            raise CommandError('Passwords do not match.')

        phone = normalize_phone(phone_raw)
        if not phone:
            raise CommandError('Enter a valid 10-digit mobile number.')
        if not USERNAME_RE.match(username):
            raise CommandError('Username must be 3-30 characters: letters, numbers, underscore or dot.')
        if len(password) < 6:
            raise CommandError('Password must be at least 6 characters.')
        if User.objects.filter(username__iexact=username).exists():
            raise CommandError('That username already exists.')
        if UserProfile.objects.filter(phone=phone).exists():
            raise CommandError('That phone number is already used by another account.')

        # superuser=True also lets this person open Django's /admin/ site
        create_account(username, name, phone, password, role=UserProfile.ROLE_OWNER, superuser=True)
        self.stdout.write(self.style.SUCCESS(f'Owner "{username}" created. Log in with {phone} or "{username}".'))
