from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.parser.authentication import ParserWorkerAuthentication
from api.v1.parser.permissions import CanManageParserCatalog, IsParserWorker
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
        company_id = get_object_or_404(Link.objects.only("company_id"), pk=pk).company_id
        get_object_or_404(Company.objects.select_for_update(), pk=company_id)
        source = get_object_or_404(
            Link.objects.select_for_update(of=("self",)).select_related("company", "category"), pk=pk
        )
        if source.company_id != company_id:
            raise ParserCatalogConflict("Source ownership changed. Reload and retry.")
        return source

    def worker_name(self, request, serializer=None):
        return (request.user.get_full_name() or request.user.email or f"user-{request.user.pk}")[:100]


class ParserWorkerAPIView(ParserWorkerAccessMixin, APIView):
    pass


class ParserCatalogWriteMixin:
    def save_catalog(self, serializer):
        creating = serializer.instance is None
        try:
            with transaction.atomic():
                instance = serializer.save()
                LogEntry.objects.log_actions(
                    user_id=self.request.user.pk,
                    queryset=[instance],
                    action_flag=ADDITION if creating else CHANGE,
                    change_message=(
                        [{"added": {}}] if creating else [{"changed": {"fields": sorted(serializer.validated_data)}}]
                    ),
                )
        except IntegrityError as exc:
            raise ParserCatalogConflict("Catalog write conflict. Reload and retry with unique values.") from exc

    def perform_create(self, serializer):
        self.save_catalog(serializer)


class ParserSourceListView(ParserCatalogWriteMixin, ListCreateAPIView):
    authentication_classes = [ParserWorkerAuthentication]
    permission_classes = [CanManageParserCatalog]
    catalog_model = "link"
    serializer_class = ParserSourceSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            # Creation and reassignment join the same company lock protocol as leases.
            company = get_object_or_404(Company.objects.select_for_update(), pk=serializer.validated_data["company"].pk)
            serializer.validated_data["company"] = company
            self.save_catalog(serializer)

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


class ParserSourceDetailView(ParserCatalogWriteMixin, ParserWorkerAccessMixin, RetrieveUpdateAPIView):
    permission_classes = [CanManageParserCatalog]
    catalog_model = "link"
    serializer_class = ParserSourceSerializer
    queryset = Link.objects.select_related("company", "category")

    def update(self, request, *args, **kwargs):
        initial = self.get_object()
        candidate = self.get_serializer(initial, data=request.data, partial=kwargs.get("partial", False))
        candidate.is_valid(raise_exception=True)
        company_ids = {initial.company_id, candidate.validated_data.get("company", initial.company).pk}
        with transaction.atomic():
            # Lock both companies in ID order for reassignment, then the source.
            list(Company.objects.filter(pk__in=company_ids).order_by("pk").select_for_update())
            self.queryset = self.queryset.select_for_update(of=("self",))
            locked = self.get_object()
            if locked.company_id != initial.company_id:
                raise ParserCatalogConflict("Source ownership changed. Reload and retry.")
            return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        source = serializer.instance
        if source.is_lease_active():
            raise ParserCatalogConflict("Source is currently leased. Retry after the run finishes.")
        changes_identity = any(
            field in serializer.validated_data and serializer.validated_data[field].pk != getattr(source, f"{field}_id")
            for field in ("company", "category")
        )
        if changes_identity and (source.products.exists() or source.parser_attempts.exists()):
            raise ValidationError("Create a new source to change company/category after ingestion or attempts.")
        self.save_catalog(serializer)


class ParserCatalogConflict(ValidationError):
    status_code = status.HTTP_409_CONFLICT


class ParserCompanyListView(ParserCatalogWriteMixin, ParserWorkerAccessMixin, ListCreateAPIView):
    permission_classes = [CanManageParserCatalog]
    catalog_model = "company"
    serializer_class = ParserCompanySerializer
    pagination_class = ParserCatalogPagination

    def get_queryset(self):
        return (
            Company.objects.select_related("location__country", "location__region")
            .annotate(source_count=Count("links"))
            .order_by("name", "id")
        )


class ParserCompanyDetailView(ParserCatalogWriteMixin, ParserWorkerAccessMixin, RetrieveUpdateAPIView):
    permission_classes = [CanManageParserCatalog]
    catalog_model = "company"
    serializer_class = ParserCompanySerializer
    queryset = Company.objects.select_related("location__country", "location__region").annotate(
        source_count=Count("links")
    )

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            get_object_or_404(Company.objects.select_for_update(), pk=kwargs["pk"])
            # All API lease/creation/reassignment paths lock the company first.
            self.leased_sources = Link.objects.filter(
                company_id=kwargs["pk"],
                lease_token__isnull=False,
                leased_until__gt=timezone.now(),
            ).exists()
            return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        if (
            "parser_map" in serializer.validated_data
            and serializer.validated_data["parser_map"] != serializer.instance.parser_map
            and self.leased_sources
        ):
            raise ParserCatalogConflict("Company has leased sources. Retry configuration edits after they finish.")
        self.save_catalog(serializer)


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
            submitted_map = serializer.validated_data.get("parser_config")
            if submitted_map is not None and submitted_map != (source.parser_map or source.company.parser_map or {}):
                raise ParserCatalogConflict("Parser configuration changed. Reload the source before running again.")
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
