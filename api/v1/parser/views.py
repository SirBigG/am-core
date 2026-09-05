from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.parser.authentication import ParserWorkerAuthentication
from api.v1.parser.permissions import IsParserWorker
from api.v1.parser.serializers import (
    LeaseResponseSerializer,
    LeaseSerializer,
    ParserCategorySerializer,
    ParserCompanySerializer,
    ParserFailureSerializer,
    ParserPriceHistorySerializer,
    ParserProductSerializer,
    ParserResultsSerializer,
    ParserSourceAttemptSerializer,
    ParserSourceQuerySerializer,
    ParserSourceSerializer,
)
from core.classifier.models import Category
from core.companies.models import (
    Company,
    Link,
    ParserSourceAttempt,
    Product,
    ProductPriceHistory,
    get_minimum_parser_crawl_interval_minutes,
    get_parser_failure_retry_minutes,
)


class ParserCatalogPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class ParserWorkerAccessMixin:
    authentication_classes = [ParserWorkerAuthentication]
    permission_classes = [IsParserWorker]

    def get_source(self, pk):
        return get_object_or_404(Link.objects.select_related("company", "category"), pk=pk)

    def get_locked_source(self, pk):
        return get_object_or_404(Link.objects.select_for_update().select_related("company", "category"), pk=pk)

    def worker_name(self, request, serializer=None):
        return (request.user.get_full_name() or request.user.email or f"user-{request.user.pk}")[:100]


class ParserWorkerAPIView(ParserWorkerAccessMixin, APIView):
    pass


class ParserSourceListView(ListAPIView):
    authentication_classes = [ParserWorkerAuthentication]
    permission_classes = [IsParserWorker]
    serializer_class = ParserSourceSerializer

    def get_queryset(self):
        now = timezone.now()
        query_serializer = ParserSourceQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)
        query_params = query_serializer.validated_data
        queryset = Link.objects.select_related("company", "category")
        if query_params["scope"] == "due":
            queryset = (
                queryset.filter(active=True)
                .filter(Q(leased_until__isnull=True) | Q(leased_until__lte=now))
                .filter(Q(last_error_at__isnull=True) | Q(last_error_at__lte=self.failure_retry_before_sql(now)))
                .filter(Q(last_crawled__isnull=True) | Q(last_crawled__lte=self.due_before_sql(now)))
            )
        elif self.request.query_params.get("active") is not None:
            queryset = queryset.filter(active=query_params["active"])
        company = query_params.get("company")
        if company:
            queryset = queryset.filter(company_id=company)
        category = query_params.get("category")
        if category:
            category_filter = Q(category__slug=category)
            if category.isdigit():
                category_filter |= Q(category_id=category)
            queryset = queryset.filter(category_filter)
        experiment = query_params.get("experiment")
        if experiment:
            queryset = queryset.filter(experiment_label=experiment)
        if query_params["scope"] == "all" and "after_id" in query_params:
            return queryset.filter(id__gt=query_params["after_id"]).order_by("id")[: query_params["limit"]]
        return queryset.order_by("priority", "last_crawled", "id")[: query_params["limit"]]

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
            force = serializer.validated_data["force"]
            if force and not request.user.has_perm("companies.run_parser_source_on_demand"):
                return Response({"detail": "On-demand parser permission required."}, status=status.HTTP_403_FORBIDDEN)
            if not force and not source.is_due():
                return Response({"detail": "Source is not due for crawling."}, status=status.HTTP_409_CONFLICT)
            source.lease(self.worker_name(request, serializer), serializer.validated_data["duration_minutes"])
        return Response(LeaseResponseSerializer(source).data)


class ParserSourceDetailView(ParserWorkerAccessMixin, RetrieveAPIView):
    serializer_class = ParserSourceSerializer
    queryset = Link.objects.select_related("company", "category")


class ParserCompanyListView(ParserWorkerAccessMixin, ListAPIView):
    serializer_class = ParserCompanySerializer
    pagination_class = ParserCatalogPagination

    def get_queryset(self):
        return (
            Company.objects.select_related("location__country", "location__region")
            .annotate(source_count=Count("links"))
            .order_by("name", "id")
        )


class ParserCategoryListView(ParserWorkerAccessMixin, ListAPIView):
    serializer_class = ParserCategorySerializer
    pagination_class = ParserCatalogPagination

    def get_queryset(self):
        return (
            Category.objects.filter(links__isnull=False)
            .annotate(source_count=Count("links"))
            .order_by("tree_id", "lft")
        )


class ParserSourceAttemptListView(ParserWorkerAccessMixin, ListAPIView):
    serializer_class = ParserSourceAttemptSerializer
    pagination_class = ParserCatalogPagination

    def get_queryset(self):
        queryset = ParserSourceAttempt.objects.select_related("source_link")
        source_id = self.request.query_params.get("source")
        status_value = self.request.query_params.get("status")
        if source_id and source_id.isdigit():
            queryset = queryset.filter(source_link_id=source_id)
        if status_value in dict(ParserSourceAttempt.STATUS_CHOICES):
            queryset = queryset.filter(status=status_value)
        return queryset


class ParserProductListView(ParserWorkerAccessMixin, ListAPIView):
    serializer_class = ParserProductSerializer
    pagination_class = ParserCatalogPagination

    def get_queryset(self):
        queryset = Product.objects.select_related("company", "category", "source_link").order_by("name", "id")
        filters = {
            "source_link_id": self.request.query_params.get("source"),
            "company_id": self.request.query_params.get("company"),
            "category_id": self.request.query_params.get("category"),
        }
        for field, value in filters.items():
            if value and value.isdigit():
                queryset = queryset.filter(**{field: value})
        active = self.request.query_params.get("active")
        if active in {"true", "1"}:
            queryset = queryset.filter(active=True)
        elif active in {"false", "0"}:
            queryset = queryset.filter(active=False)
        return queryset


class ParserPriceHistoryListView(ParserWorkerAccessMixin, ListAPIView):
    serializer_class = ParserPriceHistorySerializer
    pagination_class = ParserCatalogPagination

    def get_queryset(self):
        queryset = ProductPriceHistory.objects.select_related("product", "source_link")
        source_id = self.request.query_params.get("source")
        product_id = self.request.query_params.get("product")
        if source_id and source_id.isdigit():
            queryset = queryset.filter(source_link_id=source_id)
        if product_id and product_id.isdigit():
            queryset = queryset.filter(product_id=product_id)
        return queryset


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
                completed_attempt = ParserSourceAttempt.objects.filter(
                    source_link=source,
                    worker_name=worker_name,
                    lease_token=serializer.validated_data["lease_token"],
                    status=ParserSourceAttempt.STATUS_SUCCESS,
                ).first()
                if completed_attempt:
                    return Response(
                        {"count": completed_attempt.product_count, "replayed": True},
                        status=status.HTTP_200_OK,
                    )
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
                completed_attempt = ParserSourceAttempt.objects.filter(
                    source_link=source,
                    worker_name=worker_name,
                    lease_token=serializer.validated_data["lease_token"],
                    status=ParserSourceAttempt.STATUS_FAILURE,
                ).first()
                if completed_attempt:
                    return Response(
                        {"status": "recorded", "replayed": True},
                        status=status.HTTP_200_OK,
                    )
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
                parser_config_version=serializer.validated_data.get(
                    "parser_config_version", source.parser_config_version
                ),
                parser_config=serializer.validated_data.get(
                    "parser_config", source.parser_map or source.company.parser_map or {}
                ),
            )
        return Response({"status": "recorded"}, status=status.HTTP_200_OK)
