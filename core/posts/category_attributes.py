from decimal import Decimal, InvalidOperation

from django import forms

from core.posts.models import (
    CategoryAttributeChoice,
    CategoryAttributeField,
    CategoryAttributeFieldType,
    PostAttributeValue,
)

ATTRIBUTE_FIELD_PREFIX = "category_attribute_"


def attribute_form_field_name(field):
    return f"{ATTRIBUTE_FIELD_PREFIX}{field.pk}"


def get_category_attributes_for_post(post, category_id=None):
    category_id = category_id or post.rubric_id
    if not category_id:
        return {}
    attributes = post.category_attributes or {}
    return dict(attributes.get(str(category_id), {}))


def set_category_attributes_for_post(post, category_id, values):
    attributes = dict(post.category_attributes or {})
    category_key = str(category_id)
    if values:
        attributes[category_key] = values
    else:
        attributes.pop(category_key, None)
    post.category_attributes = attributes


def get_category_schema_fields(category_id):
    if not category_id:
        return CategoryAttributeField.objects.none()
    return (
        CategoryAttributeField.objects.select_related("group")
        .prefetch_related("choices")
        .filter(category_id=category_id, is_active=True)
        .order_by("group__sort_order", "sort_order", "label")
    )


def build_form_field(field):
    choices = [(choice.value, choice.label) for choice in field.choices.filter(is_active=True)]
    if field.field_type == CategoryAttributeFieldType.SELECT:
        return forms.ChoiceField(
            label=field.label,
            choices=(("", "---------"), *choices),
            required=field.is_required,
            help_text=field.help_text,
        )
    if field.field_type == CategoryAttributeFieldType.MULTISELECT:
        return forms.MultipleChoiceField(
            label=field.label,
            choices=choices,
            required=field.is_required,
            help_text=field.help_text,
            widget=forms.CheckboxSelectMultiple,
        )
    if field.field_type == CategoryAttributeFieldType.BOOLEAN:
        return forms.BooleanField(label=field.label, required=False, help_text=field.help_text)
    if field.field_type == CategoryAttributeFieldType.INTEGER:
        return forms.IntegerField(label=field.label, required=field.is_required, help_text=field.help_text)
    if field.field_type == CategoryAttributeFieldType.DECIMAL:
        return forms.DecimalField(
            label=field.label,
            required=field.is_required,
            decimal_places=field.decimal_places or None,
            help_text=field.help_text,
        )
    if field.field_type == CategoryAttributeFieldType.RANGE:
        return forms.CharField(
            label=field.label,
            required=field.is_required,
            help_text=field.help_text or "Use 120-150, 220, max 220, or from 120.",
        )
    return forms.CharField(label=field.label, required=field.is_required, help_text=field.help_text)


def normalize_attribute_value(field, value):
    if value in (None, "", [], ()):
        return None
    if field.field_type == CategoryAttributeFieldType.MULTISELECT:
        return [item for item in value if item]
    if field.field_type == CategoryAttributeFieldType.BOOLEAN:
        return bool(value)
    if field.field_type in (CategoryAttributeFieldType.INTEGER, CategoryAttributeFieldType.DECIMAL):
        return str(value)
    if field.field_type == CategoryAttributeFieldType.RANGE:
        return normalize_range_value(value)
    return value


def normalize_range_value(value):
    if isinstance(value, dict):
        min_value = value.get("min")
        max_value = value.get("max")
        normalized = {}
        if min_value not in (None, ""):
            normalized["min"] = str(_to_decimal(min_value))
        if max_value not in (None, ""):
            normalized["max"] = str(_to_decimal(max_value))
        return normalized or None

    text = str(value).strip().lower()
    if not text:
        return None
    text = text.replace("–", "-").replace("—", "-")

    if text.startswith(("max ", "до ")):
        return {"max": str(_to_decimal(text.split(" ", 1)[1]))}
    if text.startswith(("from ", "від ")):
        return {"min": str(_to_decimal(text.split(" ", 1)[1]))}
    if "-" in text:
        min_value, max_value = text.split("-", 1)
        return {
            "min": str(_to_decimal(min_value)),
            "max": str(_to_decimal(max_value)),
        }

    number = str(_to_decimal(text))
    return {"min": number, "max": number}


def range_value_to_display(value):
    if not isinstance(value, dict):
        return value or ""
    min_value = value.get("min")
    max_value = value.get("max")
    if min_value and max_value and min_value == max_value:
        return min_value
    if min_value and max_value:
        return f"{min_value}-{max_value}"
    if max_value:
        return f"max {max_value}"
    if min_value:
        return f"from {min_value}"
    return ""


def get_public_category_attribute_groups(post):
    attributes = get_category_attributes_for_post(post)
    if not attributes:
        return []

    groups = []
    current_group_key = None
    current_group = None
    fields = get_category_schema_fields(post.rubric_id).filter(is_public=True)
    for field in fields:
        value = attributes.get(field.key)
        if value in (None, "", [], ()):
            continue
        display_value = attribute_value_to_display(field, value)
        if not display_value:
            continue

        group_key = field.group_id or 0
        if group_key != current_group_key:
            current_group_key = group_key
            current_group = {
                "title": field.group.title if field.group else "Характеристики",
                "fields": [],
            }
            groups.append(current_group)
        current_group["fields"].append(
            {
                "label": field.label,
                "value": display_value,
                "unit": field.unit,
            }
        )
    return groups


def attribute_value_to_display(field, value):
    if field.field_type == CategoryAttributeFieldType.SELECT:
        return _choice_label(field, value)
    if field.field_type == CategoryAttributeFieldType.MULTISELECT:
        labels = [_choice_label(field, item) for item in value]
        return ", ".join(label for label in labels if label)
    if field.field_type == CategoryAttributeFieldType.BOOLEAN:
        return "Так" if value else "Ні"
    if field.field_type == CategoryAttributeFieldType.RANGE:
        return range_value_to_display(value)
    if field.field_type in (CategoryAttributeFieldType.INTEGER, CategoryAttributeFieldType.DECIMAL):
        return str(value)
    return value


def rebuild_post_attribute_values(post):
    if not post.pk:
        return

    PostAttributeValue.objects.filter(post=post).delete()
    if not post.rubric_id:
        return

    attributes = get_category_attributes_for_post(post)
    if not attributes:
        return

    fields = get_category_schema_fields(post.rubric_id).filter(is_filterable=True)
    for field in fields:
        value = attributes.get(field.key)
        if value in (None, "", [], ()):
            continue
        _create_index_values(post, field, value)


def _create_index_values(post, field, value):
    if field.field_type == CategoryAttributeFieldType.SELECT:
        choice = _choice_for_value(field, value)
        if choice:
            PostAttributeValue.objects.create(
                post=post,
                category=post.rubric,
                field=field,
                choice=choice,
                value_text=choice.value,
            )
        return

    if field.field_type == CategoryAttributeFieldType.MULTISELECT:
        for item in value:
            choice = _choice_for_value(field, item)
            if choice:
                PostAttributeValue.objects.create(
                    post=post,
                    category=post.rubric,
                    field=field,
                    choice=choice,
                    value_text=choice.value,
                )
        return

    if field.field_type == CategoryAttributeFieldType.BOOLEAN:
        PostAttributeValue.objects.create(
            post=post,
            category=post.rubric,
            field=field,
            value_boolean=bool(value),
        )
        return

    if field.field_type in (CategoryAttributeFieldType.INTEGER, CategoryAttributeFieldType.DECIMAL):
        PostAttributeValue.objects.create(
            post=post,
            category=post.rubric,
            field=field,
            value_number=_to_decimal(value),
        )
        return

    if field.field_type == CategoryAttributeFieldType.RANGE and isinstance(value, dict):
        PostAttributeValue.objects.create(
            post=post,
            category=post.rubric,
            field=field,
            value_number_min=_optional_decimal(value.get("min")),
            value_number_max=_optional_decimal(value.get("max")),
        )


def _choice_for_value(field, value):
    return CategoryAttributeChoice.objects.filter(field=field, value=value, is_active=True).first()


def _choice_label(field, value):
    choice = field.choices.filter(value=value, is_active=True, is_public=True).first()
    return choice.label if choice else ""


def _optional_decimal(value):
    if value in (None, ""):
        return None
    return _to_decimal(value)


def _to_decimal(value):
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as error:
        raise forms.ValidationError("Enter a valid number.") from error
