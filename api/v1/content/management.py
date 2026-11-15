"""Shared access, audit and transaction handling for crop setup writes."""

import logging

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.db import IntegrityError, transaction
from django.utils.cache import add_never_cache_headers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser

from .hubs import HubPermissions
from .views import ContentTokenMixin


def audit(request, instance, action, fields=()):
    messages = {
        ADDITION: [{"added": {}}],
        CHANGE: [{"changed": {"fields": sorted(fields)}}],
        DELETION: [{"deleted": {"name": str(instance._meta.verbose_name), "object": str(instance)}}],
    }
    LogEntry.objects.log_actions(
        user_id=request.user.pk,
        queryset=[instance],
        action_flag=action,
        change_message=messages[action],
    )


class CropSetupAccess(ContentTokenMixin):
    permission_classes = (IsAdminUser, HubPermissions)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        add_never_cache_headers(response)
        return response

    def mutate(self, callback):
        self.uploaded_files = []
        try:
            with transaction.atomic():
                return callback()
        except Exception as exc:
            for storage, name in self.uploaded_files:
                try:
                    storage.delete(name)
                except Exception:
                    logging.getLogger(__name__).exception("Could not remove rolled-back crop upload %s", name)
            if isinstance(exc, IntegrityError):
                raise ValidationError("Conflicting write; read current state and retry.") from exc
            raise
