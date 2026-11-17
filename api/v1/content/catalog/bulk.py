from urllib.parse import urlencode

from django.urls import reverse
from rest_framework import serializers
from rest_framework.response import Response

from core.catalog.bulk import CatalogBatch, receipt_page

from .serializers import StrictSerializer
from .views import CatalogView


class PreviewSerializer(StrictSerializer):
    operation = serializers.CharField(max_length=40)
    operation_key = serializers.CharField(max_length=128)
    items = serializers.ListField(child=serializers.DictField(), min_length=1, max_length=50)


class ApplySerializer(StrictSerializer):
    preview = serializers.CharField(max_length=3500000, trim_whitespace=False)
    payload_digest = serializers.RegexField(r"^[a-f0-9]{64}$")


class BatchPreviewView(CatalogView):
    def post(self, request):
        return Response(CatalogBatch(self.access).preview(self.body(PreviewSerializer)))


class BatchApplyView(CatalogView):
    def post(self, request):
        data = self.body(ApplySerializer)
        receipt, replayed = CatalogBatch(self.access).apply(data["preview"], data["payload_digest"])
        body, cursor = receipt_page(receipt)
        body["next"] = (
            reverse("catalog-batch-receipt", args=[receipt.pk]) + "?" + urlencode({"cursor": cursor})
            if cursor
            else None
        )
        return Response(body, headers={"Idempotent-Replay": "true" if replayed else "false"})


class BatchReceiptView(CatalogView):
    def get(self, request, receipt_id):
        params = self.query()
        receipt = CatalogBatch(self.access).receipt(receipt_id)
        size = int(params.get("page_size", 20))
        body, cursor = receipt_page(receipt, cursor=params.get("cursor"), page_size=size)
        body["next"] = (
            reverse("catalog-batch-receipt", args=[receipt.pk]) + "?" + urlencode({"cursor": cursor, "page_size": size})
            if cursor
            else None
        )
        return Response(body)
