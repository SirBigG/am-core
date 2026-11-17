from django import forms
from django.contrib import admin
from django.db import transaction

from .access_models import RelationEntityGrant, RelationSiteGrant
from .application_models import ApplicationCountryPolicy, ApplicationReviewerGrant
from .models import CatalogEntity
from .publication_eligibility import lock_publication_graph
from .relation_access import configured_relation_site


class GrantAdministration(admin.ModelAdmin):
    actions = None
    site_lookup = None

    def has_module_permission(self, request):
        # Grant provisioning can expand an editor's own publication scope.
        return request.user.is_superuser

    has_add_permission = has_module_permission

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    has_change_permission = has_delete_permission = has_view_permission

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if self.site_lookup:
            queryset = queryset.filter(**{self.site_lookup: configured_relation_site()})
        return queryset

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method != "POST" or not self.has_module_permission(request):
            return super().changeform_view(request, object_id, form_url, extra_context)
        with transaction.atomic():
            lock_publication_graph()
            return super().changeform_view(request, object_id, form_url, extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        if request.method != "POST" or not self.has_module_permission(request):
            return super().delete_view(request, object_id, extra_context)
        with transaction.atomic():
            lock_publication_graph()
            return super().delete_view(request, object_id, extra_context)


@admin.register(RelationSiteGrant)
class RelationSiteGrantAdmin(GrantAdministration):
    site_lookup = "site_id"
    fields = ("actor", "site", "can_edit", "can_review", "can_publish")
    raw_id_fields = ("actor",)
    list_display = fields
    list_select_related = ("actor", "site")
    search_fields = ("actor__email",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "site":
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(pk=configured_relation_site())
            kwargs["initial"] = configured_relation_site()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class RelationEntityGrantForm(forms.ModelForm):
    entity = forms.ModelChoiceField(
        queryset=CatalogEntity.objects.all(),
        widget=forms.TextInput,
        required=False,
        label="Catalog entity UUID",
        help_text="Leave blank to use the entity attached to the selected post or category.",
    )

    def clean(self):
        data = super().clean()
        post, category = data.get("post"), data.get("category")
        if post and category:
            self.add_error("category", "Select either a post or a category.")
            return data
        anchor = post or category
        entity = data.get("entity")
        if anchor:
            if not anchor.entity_id:
                self.add_error("entity", "The selected post or category has no catalog entity.")
            elif entity and entity.pk != anchor.entity_id:
                self.add_error("entity", "The selected post or category belongs to a different catalog entity.")
            elif "entity" not in self.errors:
                data["entity"] = anchor.entity
        elif not entity and "entity" not in self.errors:
            self.add_error("entity", "Enter an entity UUID or select its post or category.")
        return data


class SiteGrantChildAdministration(GrantAdministration):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.remote_field.model is RelationSiteGrant:
            kwargs["queryset"] = (
                RelationSiteGrant.objects.filter(site_id=configured_relation_site())
                .select_related("actor", "site")
                .order_by("actor__email")
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(RelationEntityGrant)
class RelationEntityGrantAdmin(SiteGrantChildAdministration):
    site_lookup = "grant__site_id"
    form = RelationEntityGrantForm
    fields = ("grant", "post", "category", "entity")
    raw_id_fields = ("post", "category")
    list_display = ("grant", "entity", "post", "category")
    list_select_related = ("grant__actor", "grant__site", "entity", "post", "category")
    search_fields = ("grant__actor__email", "post__title", "category__value", "entity__id")


@admin.register(ApplicationReviewerGrant)
class ApplicationReviewerGrantAdmin(SiteGrantChildAdministration):
    site_lookup = "site_grant__site_id"
    fields = ("site_grant", "country", "can_review")
    list_display = fields
    list_select_related = ("site_grant__actor", "site_grant__site", "country")
    list_filter = ("country", "can_review")
    search_fields = ("site_grant__actor__email",)


@admin.register(ApplicationCountryPolicy)
class ApplicationCountryPolicyAdmin(GrantAdministration):
    fields = ("country", "timezone_name", "active")
    list_display = fields

    def get_readonly_fields(self, request, obj=None):
        return ("country",) if obj else ()
