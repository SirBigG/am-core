from collections.abc import Mapping

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.catalog.relations import RelationTypeVersion
from core.catalog.validation import validate_database_text as require_database_text


def validate_database_text(value):
    """Keep the API field-error envelope around shared database text
    validation."""
    try:
        require_database_text(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"non_field_errors": exc.messages}) from exc


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({"non_field_errors": ["Expected a JSON object."]})
        validate_database_text(data)
        if set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["Unknown fields are not allowed."]})
        return super().to_internal_value(data)


class DraftSerializer(StrictSerializer):
    type_code = serializers.SlugField(max_length=64)
    schema_version = serializers.IntegerField(min_value=1)
    participants = serializers.DictField(child=serializers.ListField(child=serializers.UUIDField(), max_length=50))
    payload = serializers.JSONField(default=dict)
    source = serializers.JSONField(default=dict)
    country = serializers.RegexField(r"^[A-Z]{2}$", required=False, default="", allow_blank=True)
    source_version_digest = serializers.RegexField(r"^[a-f0-9]{64}$", required=False, default="", allow_blank=True)

    def validate(self, data):
        if not isinstance(data["payload"], dict) or not isinstance(data["source"], dict):
            raise serializers.ValidationError("Payload and source must be JSON objects.")
        schema = RelationTypeVersion.objects.filter(
            relation_type_id=data["type_code"], version=data["schema_version"]
        ).first()
        if schema is None:
            raise serializers.ValidationError("Relation type or schema version is unavailable.")
        if set(data["participants"]) - set(schema.roles):
            raise serializers.ValidationError("Unknown participant role.")
        return data


class ReviewSerializer(StrictSerializer):
    action = serializers.ChoiceField(choices=("approve", "reject"))
    content_locale = serializers.CharField(max_length=16, required=False, default="", allow_blank=True)

    def validate(self, data):
        if data["action"] == "approve" and not data["content_locale"]:
            raise serializers.ValidationError("Approval requires a content language.")
        return data


class ReleaseSerializer(StrictSerializer):
    revision_id = serializers.UUIDField()
    content_locale = serializers.CharField(max_length=16)


class EmptySerializer(StrictSerializer):
    pass


class WithdrawalSerializer(StrictSerializer):
    reason = serializers.CharField(max_length=2000)
    evidence = serializers.DictField(allow_empty=False)


class ReinstatementSerializer(StrictSerializer):
    revision_id = serializers.UUIDField()
    withdrawal_id = serializers.UUIDField()
    evidence = serializers.DictField(allow_empty=False)
