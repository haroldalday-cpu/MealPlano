"""Input rules from PRD Section 12, shared by the web layer and the food service."""

import re
import unicodedata
from datetime import date

from mealplano.dsa import CATEGORIES

MAX_NAME = 50
MIN_CENTAVOS = 1                  # P0.01
MAX_CENTAVOS = 10_000_000         # P100,000.00
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
MIN_PASSWORD = 8
MAX_PASSWORD = 128
_AMOUNT_RE = re.compile(r"^(\d+)(?:\.(\d{1,2}))?$")
# [0-9], not \d: in Python \d also matches other scripts' digits, e.g. full-width "２".
_DATE_RE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")
_MONTH_RE = re.compile(r"^([0-9]{4})-([0-9]{2})$")
PLAN_DAYS_BACK = 366          # the calendar accepts dates from about 1 year ago
PLAN_DAYS_AHEAD = 731         # to about 2 years ahead


class InputError(ValueError):
    """A user input broke a rule. The message is safe to show to the user."""


def normalize_name(name):
    """Trim the ends and collapse inner runs of spaces, tabs or newlines to one space.

    So "Pancit   Canton" and "Pancit Canton" are the same food.
    """
    return " ".join(str(name or "").split())


def clean_name(name):
    """Normalize spaces; the name must then be 1 to 50 printable characters."""
    name = normalize_name(name)
    if any(unicodedata.category(ch).startswith("C") for ch in name):
        raise InputError("Food names cannot contain control characters.")
    if not name:
        raise InputError("Please enter a food name.")
    if len(name) > MAX_NAME:
        raise InputError(f"Food names can be at most {MAX_NAME} characters.")
    return name


def check_category(category):
    if category not in CATEGORIES:
        raise InputError("Please choose Breakfast, Lunch, Dinner, or Snacks.")
    return category


def parse_pesos(text, what="Price"):
    """Turn user text like "80.50", "P1,200" or "₱80" into integer centavos.

    Rules: P0.01 to P100,000.00, at most 2 decimal places. Never uses float,
    so "80.10" is exactly 8010.
    """
    raw = str(text or "").strip().replace(",", "").lstrip("₱Pp").strip()
    if not raw:
        raise InputError(f"Please enter a {what.lower()}.")
    match = _AMOUNT_RE.match(raw)
    if not match:
        raise InputError(f"{what} must be a number with at most 2 decimal places, e.g. 80.50.")
    whole, cents = match.group(1), (match.group(2) or "").ljust(2, "0")
    range_error = InputError(f"{what} must be from ₱0.01 to ₱100,000.00.")
    # Check the length before int(): Python refuses to convert over 4,300 digits
    # and would crash the request (BUG_LOG.md). The maximum, 100000, has 6.
    if len(whole.lstrip("0")) > 6:
        raise range_error
    centavos = int(whole) * 100 + int(cents)
    if not MIN_CENTAVOS <= centavos <= MAX_CENTAVOS:
        raise range_error
    return centavos


def format_pesos(centavos):
    """8050 -> "₱80.50" (display only)."""
    sign = "-" if centavos < 0 else ""
    whole, cents = divmod(abs(centavos), 100)
    return f"{sign}₱{whole:,}.{cents:02d}"


def check_username(username):
    username = (username or "").strip()
    if not USERNAME_RE.match(username):
        raise InputError("Username must be 3 to 30 characters: letters, numbers, _ . or -.")
    return username


def check_password(password):
    password = password or ""
    if len(password) < MIN_PASSWORD:
        raise InputError(f"Password must be at least {MIN_PASSWORD} characters.")
    if len(password) > MAX_PASSWORD:
        raise InputError(f"Password can be at most {MAX_PASSWORD} characters.")
    return password


def date_window(today=None):
    """(earliest, latest) dates the calendar accepts."""
    today = today or date.today()
    return (date.fromordinal(today.toordinal() - PLAN_DAYS_BACK),
            date.fromordinal(today.toordinal() + PLAN_DAYS_AHEAD))


def parse_date(text, today=None):
    """Strict YYYY-MM-DD within the calendar's window, as a date."""
    match = _DATE_RE.match(str(text or "").strip())
    try:
        day = date(*(int(part) for part in match.groups())) if match else None
    except ValueError:
        day = None
    if day is None:
        raise InputError("Please choose a valid date (YYYY-MM-DD).")
    earliest, latest = date_window(today)
    if not earliest <= day <= latest:
        raise InputError(f"Choose a date from {earliest:%d %b %Y} to {latest:%d %b %Y}.")
    return day


def parse_month(text, today=None):
    """YYYY-MM as (year, month). Anything invalid or outside the window falls back to this month."""
    today = today or date.today()
    match = _MONTH_RE.match(str(text or "").strip())
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        earliest, latest = date_window(today)
        if 1 <= month <= 12 and (earliest.year, earliest.month) <= (year, month) <= (latest.year, latest.month):
            return year, month
    return today.year, today.month


def parse_optional_pesos(text, what):
    """Like parse_pesos, but a blank box means "not set" (None)."""
    if not str(text or "").strip():
        return None
    return parse_pesos(text, what)
