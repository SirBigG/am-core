"""Explicit hub revision/preview/publish forms; all writes use BlockAccess."""

import json

from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.cache import add_never_cache_headers

from core.classifier.publication_checks import SiteContentPolicy

from .blocks import BlockAccess, block_presets
from .relation_access import configured_relation_site


class ConfigurationForm(forms.Form):
    version = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)
    blocks = forms.JSONField(
        widget=forms.Textarea(attrs={"rows": 24}), help_text="One to three ordered declarative blocks."
    )


class PreviewForm(forms.Form):
    revision_id = forms.UUIDField()
    country = forms.RegexField(r"^[A-Z]{2}$", max_length=2)


class ActivationForm(forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    preview = forms.CharField(widget=forms.HiddenInput)


def hub_blocks_view(admin, request, hub_id):
    if request.method not in {"GET", "POST"}:
        return HttpResponseNotAllowed(["GET", "POST"])
    if request.method == "GET" and not request.GET:
        BlockAccess(request.user, configured_relation_site())._grant()
        policy = SiteContentPolicy.objects.filter(site_id=configured_relation_site(), active=True).first()
        form = forms.Form()
        locales = policy.content_locales if policy and isinstance(policy.content_locales, list) else []
        form.fields["content_locale"] = forms.ChoiceField(
            choices=[("", "Choose content language")] + [(locale_code, locale_code) for locale_code in locales]
        )
        response = TemplateResponse(
            request,
            "admin/catalog/hub_blocks.html",
            {**admin.admin_site.each_context(request), "title": "Choose block content language", "locale_form": form},
        )
        add_never_cache_headers(response)
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response
    if set(request.GET) != {"content_locale"} or len(request.GET.getlist("content_locale")) != 1:
        return HttpResponseBadRequest("Choose one explicit content_locale.")
    locale = request.GET["content_locale"]
    access = BlockAccess(request.user, configured_relation_site())
    config = access.read(hub_id, locale)
    latest = config.revisions.order_by("-number").first() if config else None
    action = request.POST.get("action") if request.method == "POST" else None
    form = ConfigurationForm(
        request.POST if action == "save" else None,
        initial={"blocks": latest.blocks if latest else [], "version": config.lock_version if config else None},
    )
    preview_form = PreviewForm(
        request.POST if action == "preview" else None, initial={"revision_id": latest.pk if latest else None}
    )
    activate_form = ActivationForm(request.POST if action == "activate" else None)
    plan, error = None, None
    try:
        if action == "save" and form.is_valid():
            access.save(hub_id, locale, form.cleaned_data["blocks"], form.cleaned_data["version"])
            return redirect(request.get_full_path())
        elif action == "preview" and preview_form.is_valid():
            plan = access.preview(
                hub_id, locale, preview_form.cleaned_data["revision_id"], preview_form.cleaned_data["country"]
            )
            activate_form = ActivationForm(initial={"preview": plan["preview"], "version": plan["lock_version"]})
        elif action == "activate" and activate_form.is_valid():
            access.activate(
                hub_id, locale, activate_form.cleaned_data["version"], activate_form.cleaned_data["preview"]
            )
            return redirect(request.get_full_path())
        elif action == "disable":
            try:
                version = int(request.POST.get("version", ""))
            except ValueError:
                raise ValidationError("Supply the current configuration version.")
            access.disable(hub_id, locale, version)
            return redirect(request.get_full_path())
        elif action not in (None, "save", "preview", "activate"):
            return HttpResponseBadRequest("Unknown configuration action.")
    except ValidationError as exc:
        error = exc.messages
    except IntegrityError:
        error = ["Conflicting write; reload and preview again."]
    response = TemplateResponse(
        request,
        "admin/catalog/hub_blocks.html",
        {
            **admin.admin_site.each_context(request),
            "title": "Related catalog blocks",
            "opts": admin.model._meta,
            "rule_examples": [
                {"title": b["title"], "json": json.dumps([b], ensure_ascii=False, indent=2)} for b in block_presets()
            ],
            "configuration": config,
            "revisions": config.revisions.order_by("-number") if config else [],
            "form": form,
            "preview_form": preview_form,
            "activate_form": activate_form,
            "plan": plan,
            "errors": error,
            "hub_url": reverse(f"{admin.admin_site.name}:classifier_categoryhub_change", args=[hub_id]),
        },
    )
    add_never_cache_headers(response)
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
