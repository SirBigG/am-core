"""Validate integration attributes without coercing unknowns to false or
zero."""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from .category_attributes import get_category_schema_fields
from .models import CategoryAttributeFieldType


def validate_category_attributes(category, attributes):
    if not isinstance(attributes, dict):
        raise ValidationError("Category attributes must be an object keyed by category ID.")
    if set(attributes) - {str(category.pk)}:
        raise ValidationError("Only the selected category may be supplied in this attribute update.")
    values = attributes.get(str(category.pk), {})
    if not isinstance(values, dict):
        raise ValidationError("Category values must be an object.")
    fields = {field.key: field for field in get_category_schema_fields(category.pk)}
    if set(values) - set(fields):
        raise ValidationError("Unknown or inactive category attribute keys.")
    normalized = {}
    for key, field in fields.items():
        value = values.get(key)
        if value in (None, "", []):
            if field.is_required:
                raise ValidationError(f"{key}: required value is missing.")
            continue
        if field.field_type == CategoryAttributeFieldType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValidationError(f"{key}: supply JSON true or false.")
        elif field.field_type in (CategoryAttributeFieldType.SELECT, CategoryAttributeFieldType.MULTISELECT):
            selected = value if field.field_type == CategoryAttributeFieldType.MULTISELECT else [value]
            if not isinstance(selected, list) or not all(isinstance(v, str) for v in selected):
                raise ValidationError(f"{key}: invalid choice value type.")
            allowed = set(field.choices.filter(is_active=True).values_list("value", flat=True))
            if any(v not in allowed for v in selected) or len(set(selected)) != len(selected):
                raise ValidationError(f"{key}: unknown, inactive or duplicate choice.")
        elif field.field_type in (
            CategoryAttributeFieldType.INTEGER,
            CategoryAttributeFieldType.DECIMAL,
            CategoryAttributeFieldType.RANGE,
        ):
            if field.field_type == CategoryAttributeFieldType.RANGE:
                if not isinstance(value, dict) or not value or set(value) - {"min", "max"}:
                    raise ValidationError(f"{key}: supply min/max range bounds.")
                parts = value
            else:
                parts = {"number": value}
            converted = {}
            for bound, raw in parts.items():
                if raw is None or isinstance(raw, (bool, dict, list)):
                    raise ValidationError(f"{key}: invalid numeric value.")
                try:
                    number = Decimal(str(raw))
                except InvalidOperation, ValueError:
                    raise ValidationError(f"{key}: invalid numeric value.") from None
                if not number.is_finite() or abs(number) >= Decimal("10000000000"):
                    raise ValidationError(f"{key}: numeric value is outside index precision.")
                if field.field_type == CategoryAttributeFieldType.INTEGER and number != number.to_integral_value():
                    raise ValidationError(f"{key}: supply a whole number.")
                if number.as_tuple().exponent < -min(field.decimal_places, 4):
                    raise ValidationError(f"{key}: too many decimal places.")
                if (
                    field.min_value is not None
                    and number < field.min_value
                    or field.max_value is not None
                    and number > field.max_value
                ):
                    raise ValidationError(f"{key}: value outside field bounds.")
                converted[bound] = str(number)
            if "min" in converted and "max" in converted and Decimal(converted["min"]) > Decimal(converted["max"]):
                raise ValidationError(f"{key}: range minimum exceeds maximum.")
            value = converted if field.field_type == CategoryAttributeFieldType.RANGE else converted["number"]
        normalized[key] = value
    return {str(category.pk): normalized} if normalized else {}
