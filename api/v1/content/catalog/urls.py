from django.urls import path

from .bulk import BatchApplyView, BatchPreviewView, BatchReceiptView
from .provisioning import EntityProvisioningView
from .views import (
    AuditView,
    EntitiesView,
    EntityTypesView,
    OperationView,
    RecordActionView,
    RelationDetailView,
    RelationsView,
    RelationTypesView,
    RevisionActionView,
    RevisionsView,
)

urlpatterns = [
    path("imports/dry-run/", BatchPreviewView.as_view(), name="catalog-batch-preview"),
    path("imports/apply/", BatchApplyView.as_view(), name="catalog-batch-apply"),
    path("imports/<int:receipt_id>/", BatchReceiptView.as_view(), name="catalog-batch-receipt"),
    path(
        "relations/<str:record_id>/withdraw/",
        RecordActionView.as_view(),
        {"action": "withdraw"},
        name="catalog-withdraw",
    ),
    path(
        "relations/<str:record_id>/reinstate/",
        RecordActionView.as_view(),
        {"action": "reinstate"},
        name="catalog-reinstate",
    ),
    path("entity-types/", EntityTypesView.as_view(), name="catalog-entity-types"),
    path("relation-types/", RelationTypesView.as_view(), name="catalog-relation-types"),
    path("entities/", EntitiesView.as_view(), name="catalog-entities"),
    path("entities/provision/", EntityProvisioningView.as_view(), name="catalog-provision-entity"),
    path("relations/", RelationsView.as_view(), name="catalog-relations"),
    path("relations/<str:record_id>/", RelationDetailView.as_view(), name="catalog-relation"),
    path("relations/<str:record_id>/revisions/", RevisionsView.as_view(), name="catalog-revisions"),
    path("relations/<str:record_id>/audit/", AuditView.as_view(), name="catalog-audit"),
    path(
        "relations/<str:record_id>/release/", RecordActionView.as_view(), {"action": "release"}, name="catalog-release"
    ),
    path(
        "relations/<str:record_id>/unrelease/",
        RecordActionView.as_view(),
        {"action": "unrelease"},
        name="catalog-unrelease",
    ),
    path(
        "relations/<str:record_id>/archive/", RecordActionView.as_view(), {"action": "archive"}, name="catalog-archive"
    ),
    path(
        "revisions/<str:revision_id>/submit/",
        RevisionActionView.as_view(),
        {"action": "submit"},
        name="catalog-submit",
    ),
    path(
        "revisions/<str:revision_id>/review/",
        RevisionActionView.as_view(),
        {"action": "review"},
        name="catalog-review",
    ),
    path("operations/<str:operation_key>/", OperationView.as_view(), name="catalog-operation"),
]
