"""Hub-management extension sharing the exact Admin configuration policy."""

from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.catalog.blocks import BlockAccess
from core.catalog.relation_access import configured_relation_site

from .catalog.views import CatalogError, CatalogView


def configuration_data(configuration):
    if configuration is None:
        return {"version": 1, "configuration": None}
    return {
        "version": 1,
        "configuration": {
            "id": str(configuration.pk),
            "hub_id": configuration.hub_id,
            "site_id": configuration.site_id,
            "content_locale": configuration.content_locale,
            "owner_id": str(configuration.owner_id),
            "etag": f'"{configuration.pk}:{configuration.lock_version}"',
            "lock_version": configuration.lock_version,
            "enabled": configuration.enabled,
            "active_revision_id": str(configuration.active_revision_id) if configuration.active_revision_id else None,
            "revisions": [
                {
                    "id": str(r.pk),
                    "number": r.number,
                    "blocks": r.blocks,
                    "actor_id": r.created_by_id,
                    "created_at": r.created_at.isoformat(),
                }
                for r in configuration.revisions.order_by("number")
            ],
            "audit": list(
                configuration.audit_events.order_by("id").values("action", "actor_id", "base_version", "occurred_at")
            ),
        },
    }


class HubBlocksView(CatalogView):
    permission_classes = (IsAdminUser,)

    def initial(self, request, *args, **kwargs):
        # This endpoint uses block permissions, not unrelated relation-record permissions.
        APIView.initial(self, request, *args, **kwargs)

    def _access(self, request):
        return BlockAccess(request.user, configured_relation_site())

    def _locale(self, request):
        if set(request.query_params) != {"content_locale"} or len(request.query_params.getlist("content_locale")) != 1:
            raise ValidationError("Supply exactly one content_locale query parameter.")
        return request.query_params["content_locale"]

    def _body(self, request, fields):
        if not isinstance(request.data, dict) or set(request.data) != set(fields):
            raise ValidationError("Use exactly the documented fields for this action.")
        return request.data

    def _base(self, request, current):
        value = request.headers.get("If-Match")
        if value is None:
            raise CatalogError(428, "precondition_required", "Supply If-Match from the current readback.")
        if current is None or value != f'"{current.pk}:{current.lock_version}"':
            raise CatalogError(409, "stale_configuration", "Reload the configuration.")
        return current.lock_version

    def get(self, request, hub_id, action=None):
        if action:
            raise CatalogError(405, "method_not_allowed", "Use POST for this action.")
        return Response(configuration_data(self._access(request).read(hub_id, self._locale(request))))

    def post(self, request, hub_id, action=None):
        locale, access = self._locale(request), self._access(request)
        current = access.read(hub_id, locale)
        if action is None:
            body = self._body(request, ["blocks"])
            if current is None:
                if request.headers.get("If-None-Match") != "*":
                    raise CatalogError(428, "precondition_required", "Use If-None-Match: * for creation.")
                base = None
            else:
                base = self._base(request, current)
            result = access.save(hub_id, locale, body["blocks"], base)
            return Response(configuration_data(result), status=201)
        if action == "preview":
            body = self._body(request, ["revision_id", "country"])
            return Response(access.preview(hub_id, locale, body["revision_id"], body["country"]))
        if action == "activate":
            body = self._body(request, ["preview"])
            return Response(
                configuration_data(access.activate(hub_id, locale, self._base(request, current), body["preview"]))
            )
        if action == "disable":
            self._body(request, [])
            return Response(configuration_data(access.disable(hub_id, locale, self._base(request, current))))
        raise ValidationError("Unknown configuration action.")
