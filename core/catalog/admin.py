from uuid import UUID, uuid4

from dal import autocomplete
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from core.classifier.publication_checks import SiteContentPolicy

from . import bulk_admin
from .application_models import ApplicationReviewerGrant
from .applications import APPLICATION_TYPE
from .relation_access import RelationAccess, configured_relation_site
from .relations import RelationAuditEvent, RelationRecord, RelationRelease, RelationType, RelationTypeVersion


def participant_label(grant):
    if grant.post_id:
        name = grant.post.title
    elif grant.category_id:
        name = grant.category.value
    else:
        name = str(grant.entity_id)
    return f"{name} · {grant.entity.get_kind_display()}"


class ParticipantChoice(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return participant_label(obj)


class DraftForm(forms.Form):
    schema = forms.IntegerField(widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)
    payload = forms.JSONField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    source = forms.JSONField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    country = forms.CharField(required=False, max_length=2)
    source_version_digest = forms.CharField(required=False, max_length=64)

    def __init__(self, *args, schema, access, autocomplete_url, **kwargs):
        super().__init__(*args, **kwargs)
        self.schema = schema
        self.roles = schema.roles
        eligible = access.participants().select_related("entity", "post", "category")
        for role, definition in schema.roles.items():
            widget = autocomplete.ModelSelect2Multiple(
                url=f"{autocomplete_url}{schema.pk}/{role}/",
                attrs={"data-placeholder": "Search participants"},
            )
            field = ParticipantChoice(
                queryset=eligible.filter(entity__kind__in=definition["kinds"]),
                required=definition["min"] > 0,
                label=f"{role} ({definition['min']}–{definition['max']})",
                widget=widget,
            )
            self.fields[f"role_{role}"] = field

    def clean(self):
        data = super().clean()
        if data.get("schema") != self.schema.pk:
            self.add_error(None, "The relation schema changed. Reload the form.")
        for role, rule in self.roles.items():
            key = f"role_{role}"
            if key in data and not rule["min"] <= len(data[key]) <= rule["max"]:
                self.add_error(key, f"Select between {rule['min']} and {rule['max']} participants.")
        return data

    def save(self, access, record_id=None):
        data = self.cleaned_data
        return access.save_draft(
            type_code=self.schema.relation_type_id,
            schema_version=self.schema.version,
            participants={role: [grant.entity_id for grant in data[f"role_{role}"]] for role in self.roles},
            payload=data["payload"],
            source=data["source"],
            country=data["country"],
            source_version_digest=data["source_version_digest"],
            record_id=record_id,
            expected_version=data["version"],
        )


class RecordActionForm(forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action = forms.ChoiceField()
    content_locale = forms.ChoiceField(required=False, label="Content language")
    reason = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={"rows": 2}))
    evidence = forms.JSONField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    withdrawal_id = forms.UUIDField(required=False)
    operation_key = forms.UUIDField(required=False, initial=uuid4, widget=forms.HiddenInput)

    def __init__(self, *args, actions, locales, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["action"].choices = actions
        codes = {code for code, label in actions}
        if not codes.intersection({"withdraw", "reinstate"}):
            for name in ("reason", "evidence", "withdrawal_id", "operation_key"):
                self.fields.pop(name)
        elif "withdraw" not in codes:
            self.fields.pop("reason")
            self.fields.pop("operation_key")
        elif "reinstate" not in codes:
            self.fields.pop("withdrawal_id")
        self.fields["content_locale"].choices = [("", "Select content language"), *[(code, code) for code in locales]]

    def clean(self):
        data = super().clean()
        if data.get("action") in {"approve", "publish"} and not data.get("content_locale"):
            self.add_error("content_locale", "Select the reviewed content language.")
        if data.get("action") in {"withdraw", "reinstate"}:
            if not isinstance(data.get("evidence"), dict) or not data["evidence"]:
                self.add_error("evidence", "Provide structured decision evidence.")
            if data["action"] == "withdraw" and (not data.get("reason") or not data.get("operation_key")):
                self.add_error(None, "Withdrawal requires a reason and operation key.")
            if data["action"] == "reinstate" and not data.get("withdrawal_id"):
                self.add_error("withdrawal_id", "Reference the current withdrawal event.")
        return data


@admin.register(RelationRecord)
class RelationRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "relation_type", "archived", "withdrawn", "lock_version")
    list_filter = ("relation_type", "archived", "withdrawn")
    list_select_related = ("relation_type",)
    actions = None
    change_list_template = "admin/catalog/relationrecord/change_list.html"

    def _access(self, request):
        return RelationAccess(request.user, configured_relation_site())

    def _allowed(self, request, permission="view_relationrecord", edit=False):
        try:
            grant = self._access(request)._grant(permission=permission)
        except PermissionDenied:
            return False
        return not edit or grant.can_edit

    def has_module_permission(self, request):
        return self._allowed(request)

    def has_view_permission(self, request, obj=None):
        return self._allowed(request) and (obj is None or self._access(request).records().filter(pk=obj.pk).exists())

    def has_add_permission(self, request):
        return self._allowed(request, "add_relationrecord", edit=True)

    def has_change_permission(self, request, obj=None):
        return self._allowed(request, "change_relationrecord", edit=True) and self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        if not self._allowed(request):
            return RelationRecord.objects.none()
        return self._access(request).records()

    def get_urls(self):
        wrap = self.admin_site.admin_view
        return [
            path("bulk/", wrap(self.bulk_view), name="catalog_relation_bulk"),
            path(
                "bulk/receipts/<int:receipt_id>/", wrap(self.bulk_receipt_view), name="catalog_relation_batch_receipt"
            ),
            path("participant/<uuid:entity_id>/", wrap(self.participant_view), name="catalog_relation_participant"),
            path("participants/", wrap(self.participants_view), name="catalog_relation_participants"),
            path(
                "autocomplete/<int:schema_id>/<slug:role>/",
                wrap(self.autocomplete_view),
                name="catalog_relation_autocomplete",
            ),
        ] + super().get_urls()

    def _render(self, request, template, **context):
        return TemplateResponse(
            request,
            f"admin/catalog/relationrecord/{template}.html",
            {**self.admin_site.each_context(request), "opts": self.model._meta, **context},
        )

    def bulk_view(self, request):
        return bulk_admin.bulk_view(self, request)

    def bulk_receipt_view(self, request, receipt_id):
        return bulk_admin.bulk_receipt_view(self, request, receipt_id)

    def participants_view(self, request):
        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])
        qs = self._access(request).participants().select_related("entity", "post", "category")
        term = request.GET.get("q", "").strip()[:200]
        if term:
            qs = qs.filter(self._search(term))
        return self._render(
            request,
            "participants",
            title="Relation participants",
            term=term,
            rows=[(p.entity_id, participant_label(p)) for p in qs.order_by("entity_id")[:50]],
        )

    @staticmethod
    def _search(term):
        query = (
            Q(post__title__icontains=term)
            | Q(category__value__icontains=term)
            | Q(entity__kind__icontains=term)
            | Q(post__rubric__value__icontains=term)
        )
        try:
            return query | Q(entity_id=UUID(term))
        except ValueError:
            return query

    def autocomplete_view(self, request, schema_id, role):
        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])
        qs = self._access(request).participants()
        schema = RelationTypeVersion.objects.filter(pk=schema_id).first()
        if not schema or role not in schema.roles:
            raise Http404("Relation role is unavailable.")
        qs = qs.filter(entity__kind__in=schema.roles[role]["kinds"])
        term = request.GET.get("q", "").strip()[:200]
        if term:
            qs = qs.filter(self._search(term))
        for key in ("kind", "category"):
            value = request.GET.get(key)
            if key == "kind" and value:
                qs = qs.filter(entity__kind=value)
            if key == "category" and value:
                if not value.isascii() or not value.isdecimal() or len(value) > 9:
                    return JsonResponse({"error": "Invalid category."}, status=400)
                qs = qs.filter(Q(category_id=int(value)) | Q(post__rubric_id=int(value)))
        page = request.GET.get("page", "1")
        if not page.isascii() or not page.isdecimal() or len(page) > 5 or not int(page):
            return JsonResponse({"error": "Invalid page."}, status=400)
        start = (int(page) - 1) * 20
        rows = list(qs.select_related("entity", "post", "category").order_by("entity_id")[start : start + 21])
        return JsonResponse(
            {
                "results": [{"id": row.pk, "text": participant_label(row)} for row in rows[:20]],
                "pagination": {"more": len(rows) > 20},
            }
        )

    def participant_view(self, request, entity_id):
        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])
        access = self._access(request)
        grant = access.participants().select_related("entity", "post", "category").filter(entity_id=entity_id).first()
        if grant is None:
            raise Http404("Participant is unavailable.")
        links = access.records().filter(revisions__participants__entity_id=entity_id).distinct().order_by("id")[:100]
        return self._render(
            request,
            "participant",
            title=participant_label(grant),
            records=links,
        )

    def _draft_form(self, request, schema, initial):
        return DraftForm(
            request.POST if request.method == "POST" else None,
            schema=schema,
            access=self._access(request),
            initial=initial,
            autocomplete_url=self._autocomplete_prefix(),
        )

    def _save_draft(self, request, form, record_id=None):
        try:
            revision = form.save(self._access(request), record_id)
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(None, "The relation changed or violates its schema. Reload and check the participants.")
        else:
            self.message_user(request, "Draft saved.", messages.SUCCESS)
            return redirect(f"{self.admin_site.name}:catalog_relationrecord_change", revision.record_id)
        return None

    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        schemas = RelationTypeVersion.objects.select_related("relation_type").order_by("relation_type_id", "version")
        schema_id = request.GET.get("schema", "")
        if not schema_id:
            if request.method != "GET":
                return HttpResponseNotAllowed(["GET"])
            return self._render(request, "schemas", title="Select a relation schema", schemas=schemas)
        if not schema_id.isascii() or not schema_id.isdecimal() or len(schema_id) > 9:
            raise Http404("Relation schema is unavailable.")
        schema = schemas.filter(pk=int(schema_id)).first()
        if schema is None:
            raise Http404("Relation schema is unavailable.")
        form = self._draft_form(request, schema, {"schema": schema.pk})
        if request.method == "POST" and form.is_valid():
            response = self._save_draft(request, form)
            if response:
                return response
        return self._render(request, "record", title="Add relation draft", form=form, schema=schema)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        access = self._access(request)
        try:
            record = self.get_queryset(request).get(pk=object_id)
        except (RelationRecord.DoesNotExist, ValidationError) as exc:
            raise Http404("Relation is unavailable.") from exc
        latest = record.revisions.select_related("schema").order_by("-number").first()
        can_edit = bool(latest and self.has_change_permission(request, record) and not record.archived)
        granted = {p.entity_id: p for p in access.participants().select_related("entity", "post", "category")}
        actions = self._available_actions(request, record, latest, can_edit)
        form = action = None
        action_request = request.method == "POST" and bool(request.POST.get("action"))
        if request.method == "POST" and not (actions if action_request else can_edit):
            raise PermissionDenied
        if can_edit:
            initial = {
                "schema": latest.schema_id,
                "version": record.lock_version,
                "payload": latest.payload,
                "source": latest.source,
                "country": latest.country,
                "source_version_digest": latest.source_version_digest,
            }
            for participant in latest.participants.all():
                grant = granted.get(participant.entity_id)
                if grant is not None:
                    initial.setdefault(f"role_{participant.role}", []).append(grant.pk)
            form = DraftForm(
                request.POST if request.method == "POST" and not action_request else None,
                schema=latest.schema,
                access=access,
                initial=initial,
                autocomplete_url=self._autocomplete_prefix(),
            )
            if request.method == "POST" and not action_request and form.is_valid():
                response = self._save_draft(request, form, record.pk)
                if response:
                    return response
        current_withdrawal = record.withdrawals.order_by("-resulting_epoch").first()
        if actions:
            policy = SiteContentPolicy.objects.filter(site_id=access.site_id, active=True).first()
            locales = policy.content_locales if policy and isinstance(policy.content_locales, list) else []
            action = RecordActionForm(
                request.POST if action_request else None,
                actions=actions,
                locales=locales,
                initial={
                    "version": record.lock_version,
                    "withdrawal_id": current_withdrawal.pk if current_withdrawal else None,
                },
                auto_id="action_%s",
            )
            if action_request and action.is_valid():
                try:
                    self._apply_action(access, record, latest, action.cleaned_data)
                except ValidationError as exc:
                    action.add_error(None, exc)
                except IntegrityError:
                    action.add_error(None, "The publication changed. Reload and review the current record.")
                else:
                    return redirect(f"{self.admin_site.name}:catalog_relationrecord_change", record.pk)
        history = (
            record.revisions.select_related("schema", "created_by", "reviewed_by")
            .prefetch_related("participants")
            .order_by("-number")[:50]
        )
        revision_rows = [
            (
                revision,
                [
                    (p.role, grant.entity_id, participant_label(grant))
                    for p in revision.participants.all()
                    if (grant := granted.get(p.entity_id)) is not None
                ],
            )
            for revision in history
        ]
        return self._render(
            request,
            "record",
            title=f"Relation {record.pk}",
            record=record,
            withdrawal=current_withdrawal,
            form=form,
            schema=latest.schema if latest else None,
            action=action,
            site_release=record.releases.filter(site_id=access.site_id, enabled=True)
            .select_related("approved_revision")
            .first(),
            history=revision_rows,
            audit=RelationAuditEvent.objects.filter(record=record).select_related("actor").order_by("-pk")[:50],
        )

    def _autocomplete_prefix(self):
        return reverse(f"{self.admin_site.name}:catalog_relation_autocomplete", args=[0, "role"]).removesuffix(
            "0/role/"
        )

    def _available_actions(self, request, record, latest, can_edit):
        if not latest or record.archived:
            return []
        actions = []
        if can_edit:
            if latest.state == "draft":
                actions.append(("submit", "Submit"))
            actions.append(("archive", "Archive"))
        for permission, capability, choices in (
            ("review_relationrecord", "can_review", [("approve", "Approve"), ("reject", "Reject")]),
            ("publish_relationrecord", "can_publish", [("publish", "Publish"), ("unpublish", "Unpublish")]),
        ):
            try:
                grant = self._access(request)._grant(permission=permission)
            except PermissionDenied:
                continue
            if getattr(grant, capability):
                actions.extend(choices)
        if record.relation_type_id == APPLICATION_TYPE:
            site_grant = self._access(request)._grant()
            domain_ready = (
                site_grant.can_review
                and site_grant.can_publish
                and all(
                    request.user.has_perm(f"catalog.{code}")
                    for code in (
                        "review_relationrecord",
                        "publish_relationrecord",
                        "review_plant_protection_applications",
                    )
                )
                and ApplicationReviewerGrant.objects.filter(
                    site_grant=site_grant, country_id=latest.country, can_review=True
                ).exists()
            )
            for permission, code, label in (
                ("withdraw_relation", "withdraw", "Withdraw globally"),
                ("reinstate_relation", "reinstate", "Reinstate after review"),
            ):
                if (
                    domain_ready
                    and request.user.has_perm(f"catalog.{permission}")
                    and (
                        (code == "withdraw" and not record.withdrawn)
                        or (code == "reinstate" and record.withdrawn and latest.state == "approved")
                    )
                ):
                    actions.append((code, label))
        return actions

    @staticmethod
    def _apply_action(access, record, latest, data):
        args = {"record_id": record.pk, "expected_version": data["version"]}
        action = data["action"]
        if action == "withdraw":
            access.withdraw_application(
                **args, reason=data["reason"], evidence=data["evidence"], operation_key=str(data["operation_key"])
            )
        elif action == "reinstate":
            access.reinstate_application(
                **args, revision_id=latest.pk, withdrawal_id=data["withdrawal_id"], evidence=data["evidence"]
            )
        elif action == "submit":
            access.submit(**args, revision_id=latest.pk)
        elif action == "archive":
            access.archive(**args)
        elif action in {"approve", "reject"}:
            access.review(
                **args,
                revision_id=latest.pk,
                content_locale=data["content_locale"],
                approve=action == "approve",
            )
        else:
            revision_id = latest.pk
            if action == "unpublish":
                release = RelationRelease.objects.filter(record=record, site_id=access.site_id, enabled=True).first()
                if not release:
                    raise ValidationError("No active site release is available.")
                revision_id = release.approved_revision_id
            access.release(
                **args,
                revision_id=revision_id,
                content_locale=data["content_locale"],
                enabled=action == "publish",
            )


@admin.register(RelationType, RelationTypeVersion)
class RelationSchemaAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
