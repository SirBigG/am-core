from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.parser.authentication import ParserWorkerAuthentication
from api.v1.parser.permissions import IsParserWorker
from api.v1.parser.serializers import (
    LeaseResponseSerializer,
    LeaseSerializer,
    ParserFailureSerializer,
    ParserResultsSerializer,
    ParserSourceQuerySerializer,
    ParserSourceSerializer,
)
from core.companies.models import (
    Link,
    ParserSourceAttempt,
    get_minimum_parser_crawl_interval_minutes,
    get_parser_failure_retry_minutes,
)


class ParserWorkerAPIView(APIView):
    authentication_classes = [ParserWorkerAuthentication]
    permission_classes = [IsParserWorker]

    def get_source(self, pk):
        return get_object_or_404(Link.objects.select_related("company", "category"), pk=pk)

    def get_locked_source(self, pk):
        return get_object_or_404(Link.objects.select_for_update().select_related("company", "category"), pk=pk)

    def worker_name(self, request, serializer=None):
        return (request.user.get_full_name() or request.user.email or f"user-{request.user.pk}")[:100]


class ParserSourceListView(ListAPIView):
    authentication_classes = [ParserWorkerAuthentication]
    permission_classes = [IsParserWorker]
    serializer_class = ParserSourceSerializer

    def get_queryset(self):
        now = timezone.now()
        query_serializer = ParserSourceQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)
        query_params = query_serializer.validated_data
        queryset = (
            Link.objects.select_related("company", "category")
            .filter(active=True)
            .filter(Q(leased_until__isnull=True) | Q(leased_until__lte=now))
            .filter(Q(last_error_at__isnull=True) | Q(last_error_at__lte=self.failure_retry_before_sql(now)))
            .filter(Q(last_crawled__isnull=True) | Q(last_crawled__lte=self.due_before_sql(now)))
            .order_by("priority", "last_crawled", "id")
        )
        category = query_params.get("category")
        if category:
            category_filter = Q(category__slug=category)
            if category.isdigit():
                category_filter |= Q(category_id=category)
            queryset = queryset.filter(category_filter)
        experiment = query_params.get("experiment")
        if experiment:
            queryset = queryset.filter(experiment_label=experiment)
        return queryset[: query_params["limit"]]

    @staticmethod
    def due_before_sql(now):
        from django.db.models.expressions import RawSQL

        return RawSQL(
            "(%s::timestamptz - (GREATEST(crawl_interval_minutes, %s) * interval '1 minute'))",
            [now, get_minimum_parser_crawl_interval_minutes()],
        )

    @staticmethod
    def failure_retry_before_sql(now):
        from django.db.models.expressions import RawSQL

        return RawSQL(
            "(%s::timestamptz - (%s * interval '1 minute'))",
            [now, get_parser_failure_retry_minutes()],
        )


class ParserSourceLeaseView(ParserWorkerAPIView):
    def post(self, request, pk):
        serializer = LeaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            source = self.get_locked_source(pk)
            if source.is_lease_active():
                return Response({"detail": "Source is already leased."}, status=status.HTTP_409_CONFLICT)
            if not source.active:
                return Response({"detail": "Source is inactive."}, status=status.HTTP_409_CONFLICT)
            if not source.is_due():
                return Response({"detail": "Source is not due for crawling."}, status=status.HTTP_409_CONFLICT)
            source.lease(self.worker_name(request, serializer), serializer.validated_data["duration_minutes"])
        return Response(LeaseResponseSerializer(source).data)


class ParserSourceResultsView(ParserWorkerAPIView):
    def post(self, request, pk):
        with transaction.atomic():
            source = self.get_locked_source(pk)
            serializer = ParserResultsSerializer(
                data=request.data,
                context={"source": source, "worker_name": self.worker_name(request)},
            )
            serializer.is_valid(raise_exception=True)
            worker_name = self.worker_name(request, serializer)
            if not source.has_valid_lease(serializer.validated_data["lease_token"], worker_name):
                return Response({"detail": "Invalid or expired lease."}, status=status.HTTP_409_CONFLICT)
            products = serializer.save()
        return Response({"count": len(products)}, status=status.HTTP_200_OK)


class ParserSourceFailureView(ParserWorkerAPIView):
    def post(self, request, pk):
        with transaction.atomic():
            source = self.get_locked_source(pk)
            serializer = ParserFailureSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            worker_name = self.worker_name(request, serializer)
            if not source.has_valid_lease(serializer.validated_data["lease_token"], worker_name):
                return Response({"detail": "Invalid or expired lease."}, status=status.HTTP_409_CONFLICT)

            now = timezone.now()
            source.last_error_at = now
            source.last_crawl_status = serializer.validated_data.get("status")
            source.last_error = serializer.validated_data["error"]
            source.leased_by = None
            source.lease_token = None
            source.leased_until = None
            source.save(
                update_fields=[
                    "last_error_at",
                    "last_crawl_status",
                    "last_error",
                    "leased_by",
                    "lease_token",
                    "leased_until",
                ]
            )
            ParserSourceAttempt.objects.create(
                source_link=source,
                worker_name=worker_name,
                lease_token=serializer.validated_data["lease_token"],
                status=ParserSourceAttempt.STATUS_FAILURE,
                crawl_status=source.last_crawl_status,
                error=source.last_error,
            )
        return Response({"status": "recorded"}, status=status.HTTP_200_OK)
