from core.registry.models import Company, Variety
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView


class AddCompanyView(APIView):
    permission_classes = [
        IsAdminUser,
    ]

    def post(self, request, *args, **kwargs):
        row = request.data.get("row")
        Company.save_company_from_row(row)
        return Response({"status": "ok"})


class AddActiveVarietyView(APIView):
    permission_classes = [
        IsAdminUser,
    ]

    def post(self, request, *args, **kwargs):
        row = request.data.get("row")
        Variety.save_active_variety_from_row(row)
        return Response({"status": "ok"})


class AddInactiveVarietyView(APIView):
    permission_classes = [
        IsAdminUser,
    ]

    def post(self, request, *args, **kwargs):
        row = request.data.get("row")
        Variety.save_inactive_variety_from_row(row)
        return Response({"status": "ok"})
