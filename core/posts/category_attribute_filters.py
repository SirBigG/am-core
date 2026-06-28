from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q

from core.posts.models import CategoryAttributeFieldType, PostAttributeValue

DECIMAL_PARSE_ERRORS = (InvalidOperation, ValueError)


def apply_category_attribute_filters(queryset, category, params):
    for field in _public_filter_fields(category):
        if field.field_type in (CategoryAttributeFieldType.SELECT, CategoryAttributeFieldType.MULTISELECT):
            values = [value for value in params.getlist(_param_name(field)) if value]
            if values:
                queryset = queryset.filter(
                    pk__in=PostAttributeValue.objects.filter(
                        category=category,
                        field=field,
                        choice__value__in=values,
                    ).values("post_id")
                )
        elif field.field_type == CategoryAttributeFieldType.BOOLEAN:
            value = params.get(_param_name(field))
            if value in ("0", "1"):
                queryset = queryset.filter(
                    pk__in=PostAttributeValue.objects.filter(
                        category=category,
                        field=field,
                        value_boolean=value == "1",
                    ).values("post_id")
                )
        elif field.field_type in (
            CategoryAttributeFieldType.INTEGER,
            CategoryAttributeFieldType.DECIMAL,
            CategoryAttributeFieldType.RANGE,
        ):
            queryset = _apply_number_filter(queryset, category, field, params)
    return queryset


def build_category_attribute_filters(category, queryset, params):
    filters = []
    post_ids = queryset.values("pk")
    for field in _public_filter_fields(category):
        if field.field_type in (CategoryAttributeFieldType.SELECT, CategoryAttributeFieldType.MULTISELECT):
            options = _choice_options(field, post_ids)
            if options:
                selected = params.getlist(_param_name(field))
                filters.append(
                    {
                        "key": field.key,
                        "param": _param_name(field),
                        "input_id": _param_name(field),
                        "label": field.label,
                        "field_type": field.field_type,
                        "options": options,
                        "selected": selected,
                    }
                )
        elif field.field_type == CategoryAttributeFieldType.BOOLEAN:
            options = _boolean_options(category, field, post_ids)
            if options:
                filters.append(
                    {
                        "key": field.key,
                        "param": _param_name(field),
                        "input_id": _param_name(field),
                        "label": field.label,
                        "field_type": field.field_type,
                        "options": options,
                        "selected": params.get(_param_name(field), ""),
                    }
                )
        elif field.field_type in (
            CategoryAttributeFieldType.INTEGER,
            CategoryAttributeFieldType.DECIMAL,
            CategoryAttributeFieldType.RANGE,
        ):
            bounds = _number_bounds(category, field, post_ids)
            if bounds:
                filters.append(
                    {
                        "key": field.key,
                        "label": field.label,
                        "field_type": field.field_type,
                        "unit": field.unit,
                        "min_param": f"{_param_name(field)}_min",
                        "max_param": f"{_param_name(field)}_max",
                        "input_id": f"{_param_name(field)}_min",
                        "available_min": _format_decimal(bounds["min"], field.decimal_places),
                        "available_max": _format_decimal(bounds["max"], field.decimal_places),
                        "selected_min": params.get(f"{_param_name(field)}_min", ""),
                        "selected_max": params.get(f"{_param_name(field)}_max", ""),
                    }
                )
    return filters


def _public_filter_fields(category):
    return (
        category.attribute_fields.filter(is_active=True, is_filterable=True, is_public=True)
        .select_related("group")
        .prefetch_related("choices")
        .order_by("group__sort_order", "sort_order", "label")
    )


def _choice_options(field, post_ids):
    rows = (
        PostAttributeValue.objects.filter(
            post_id__in=post_ids,
            field=field,
            choice__is_active=True,
            choice__is_public=True,
        )
        .values("choice__value", "choice__label")
        .annotate(count=Count("pk"))
        .order_by("choice__sort_order", "choice__label")
    )
    return [
        {
            "value": row["choice__value"],
            "label": row["choice__label"],
            "count": row["count"],
        }
        for row in rows
    ]


def _boolean_options(category, field, post_ids):
    rows = (
        PostAttributeValue.objects.filter(post_id__in=post_ids, category=category, field=field)
        .values("value_boolean")
        .annotate(count=Count("pk"))
        .order_by("value_boolean")
    )
    labels = {True: "Так", False: "Ні"}
    return [
        {
            "value": "1" if row["value_boolean"] else "0",
            "label": labels[row["value_boolean"]],
            "count": row["count"],
        }
        for row in rows
        if row["value_boolean"] is not None
    ]


def _number_bounds(category, field, post_ids):
    values = PostAttributeValue.objects.filter(post_id__in=post_ids, category=category, field=field).values_list(
        "value_number",
        "value_number_min",
        "value_number_max",
    )
    mins = []
    maxes = []
    for value, min_value, max_value in values:
        if value is not None:
            mins.append(value)
            maxes.append(value)
        if min_value is not None:
            mins.append(min_value)
        if max_value is not None:
            maxes.append(max_value)
    if not mins and not maxes:
        return None
    return {
        "min": min(mins or maxes),
        "max": max(maxes or mins),
    }


def _apply_number_filter(queryset, category, field, params):
    min_value = _optional_decimal(params.get(f"{_param_name(field)}_min"))
    max_value = _optional_decimal(params.get(f"{_param_name(field)}_max"))
    if min_value is None and max_value is None:
        return queryset

    value_query = PostAttributeValue.objects.filter(category=category, field=field)
    if field.field_type in (CategoryAttributeFieldType.INTEGER, CategoryAttributeFieldType.DECIMAL):
        if min_value is not None:
            value_query = value_query.filter(value_number__gte=min_value)
        if max_value is not None:
            value_query = value_query.filter(value_number__lte=max_value)
    else:
        if min_value is not None:
            value_query = value_query.filter(Q(value_number_max__gte=min_value) | Q(value_number_min__gte=min_value))
        if max_value is not None:
            value_query = value_query.filter(Q(value_number_min__lte=max_value) | Q(value_number_max__lte=max_value))
    return queryset.filter(pk__in=value_query.values("post_id"))


def _optional_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except DECIMAL_PARSE_ERRORS:
        return None


def _format_decimal(value, decimal_places):
    if value is None:
        return ""
    if not decimal_places:
        return str(int(value))
    return f"{value:.{decimal_places}f}"


def _param_name(field):
    return f"attr_{field.key}"
