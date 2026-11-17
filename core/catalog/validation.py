"""Input text validation shared by catalog API and domain writers."""

from collections.abc import Mapping

from django.core.exceptions import ValidationError


def validate_database_text(value):
    if isinstance(value, str):
        if "\x00" in value:
            raise ValidationError("NUL characters are not supported.")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValidationError("Text must contain valid Unicode.") from exc
    elif isinstance(value, Mapping):
        for key, item in value.items():
            validate_database_text(key)
            validate_database_text(item)
    elif isinstance(value, list):
        for item in value:
            validate_database_text(item)
