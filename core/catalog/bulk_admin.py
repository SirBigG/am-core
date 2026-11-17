"""Staff bulk UI backed by the same batch service as the content API."""

from urllib.parse import urlencode

from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse

from .bulk import CatalogBatch, receipt_page


class BatchForm(forms.Form):
    batch = forms.JSONField(
        widget=forms.Textarea(attrs={"rows": 20}),
        help_text="Choose an operation, explicit participants or record IDs, and at most 50 items.",
    )


class BatchApplyForm(forms.Form):
    preview = forms.CharField(widget=forms.HiddenInput)
    payload_digest = forms.CharField(widget=forms.HiddenInput)


def bulk_view(admin, request):
    admin._access(request)._grant()
    if request.method not in {"GET", "POST"}:
        return HttpResponseNotAllowed(["GET", "POST"])
    plan = None
    form = BatchForm(request.POST if request.method == "POST" and request.POST.get("action") == "preview" else None)
    apply_form = BatchApplyForm(
        request.POST if request.method == "POST" and request.POST.get("action") == "apply" else None
    )
    service = CatalogBatch(admin._access(request))
    if request.method == "POST":
        if request.POST.get("action") == "preview" and form.is_valid():
            try:
                plan = service.preview(form.cleaned_data["batch"])
            except ValidationError as exc:
                form.add_error(None, exc.messages)
            else:
                apply_form = BatchApplyForm(
                    initial={"preview": plan["preview"], "payload_digest": plan["payload_digest"]}
                )
        elif request.POST.get("action") == "apply" and apply_form.is_valid():
            try:
                receipt, _ = service.apply(
                    apply_form.cleaned_data["preview"], apply_form.cleaned_data["payload_digest"]
                )
            except ValidationError as exc:
                apply_form.add_error(None, exc.messages)
            except IntegrityError:
                apply_form.add_error(None, "Conflicting write. Read current state and review a new preview.")
            else:
                return redirect(f"{admin.admin_site.name}:catalog_relation_batch_receipt", receipt.pk)
        elif request.POST.get("action") not in {"preview", "apply"}:
            return HttpResponseBadRequest("Unknown bulk action.")
    return admin._render(
        request, "bulk", title="Bulk catalog operations", batch_form=form, apply_form=apply_form, plan=plan
    )


def bulk_receipt_view(admin, request, receipt_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    size = request.GET.get("page_size", "20")
    if len(size) > 2 or not size.isascii() or not size.isdecimal() or not 1 <= int(size) <= 50:
        return HttpResponseBadRequest("Invalid page size.")
    service = CatalogBatch(admin._access(request))
    receipt = service.receipt(receipt_id)
    try:
        result, cursor = receipt_page(receipt, cursor=request.GET.get("cursor"), page_size=int(size))
    except ValidationError:
        return HttpResponseBadRequest("Invalid receipt cursor.")
    next_url = (
        reverse(f"{admin.admin_site.name}:catalog_relation_batch_receipt", args=[receipt.pk])
        + "?"
        + urlencode({"cursor": cursor, "page_size": size})
        if cursor
        else None
    )
    return admin._render(
        request,
        "bulk_receipt",
        title="Batch receipt",
        result=result,
        receipt_rows=[
            {
                **row,
                "details": {
                    key: value for key, value in row.items() if key not in {"key", "effect", "record_id", "revision_id"}
                },
            }
            for row in result["results"]
        ],
        next_url=next_url,
    )
