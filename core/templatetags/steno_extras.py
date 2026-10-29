"""Small template filters.  Use with  {% load steno_extras %}"""
from django import template

from core.accounts import format_phone

register = template.Library()


@register.filter
def phone_fmt(value):
    """'9211894802' -> '92118 94802'"""
    return format_phone(value) if value else ''


@register.filter
def mmss(seconds):
    """754 -> '12:34'"""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return '0:00'
    return f'{seconds // 60}:{seconds % 60:02d}'


@register.filter
def pct(value):
    """96.250 -> '96.25',  100.0 -> '100'  (accuracy / mistake rate, max 2 decimals)"""
    try:
        return f'{float(value):.2f}'.rstrip('0').rstrip('.')
    except (TypeError, ValueError):
        return value


@register.filter
def num(value):
    """12.0 -> '12',  12.5 -> '12.5'  (mistake counts can be halves)"""
    try:
        return f'{float(value):g}'
    except (TypeError, ValueError):
        return value
