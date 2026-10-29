#!/usr/bin/env python
"""Django's command-line utility (runserver, migrate, create_owner ...)."""
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'steno_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Is your virtual environment activated? "
            "(bash: source .Stenoenv/bin/activate)"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
