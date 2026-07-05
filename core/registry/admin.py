from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from mptt.admin import DraggableMPTTAdmin, TreeRelatedFieldListFilter

from core.registry.forms import RegistryImportForm
from core.registry.models import Company, RegistryImportJob, Variety, VarietyCategory


@admin.register(VarietyCategory)
class VarietyCategoryAdmin(DraggableMPTTAdmin, admin.ModelAdmin):
    pass


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "original_name", "code", "country")
    list_filter = ("country",)
    search_fields = ("name", "original_name", "code")


@admin.register(Variety)
class VarietyAdmin(admin.ModelAdmin):
    change_list_template = "admin/registry/variety/change_list.html"
    list_display = (
        "title",
        "title_original",
        "publication",
        "category",
        "original_country",
        "application_number",
        "registration_year",
        "unregister_year",
        "unregister_date",
        "recommended_zone",
        "direction_of_use",
        "ripeness_group",
    )
    list_editable = ("publication",)
    autocomplete_fields = ("publication",)
    list_filter = (
        ("category", TreeRelatedFieldListFilter),
        "registration_year",
        "unregister_year",
        "excluded",
    )
    search_fields = ("title", "title_original", "application_number")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-registry/",
                self.admin_site.admin_view(self.import_registry_view),
                name="registry_variety_import_registry",
            )
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["registry_import_url"] = reverse("admin:registry_variety_import_registry")
        return super().changelist_view(request, extra_context=extra_context)

    def import_registry_view(self, request):
        form = RegistryImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            registry_file = form.cleaned_data["registry_file"]
            job = RegistryImportJob.objects.create(
                source_file=registry_file,
                original_filename=registry_file.name,
                created_by=request.user if request.user.is_authenticated else None,
            )
            self.message_user(
                request,
                _("Registry import job #%(job_id)s queued. Run the registry import command to process it.")
                % {"job_id": job.id},
                messages.SUCCESS,
            )
            return redirect("admin:registry_registryimportjob_change", job.id)
        context = {
            **self.admin_site.each_context(request),
            "title": _("Import registry spreadsheet"),
            "opts": self.model._meta,
            "form": form,
        }
        return TemplateResponse(request, "admin/registry/variety/import_registry.html", context)


@admin.register(RegistryImportJob)
class RegistryImportJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "original_filename",
        "status",
        "created_by",
        "created_at",
        "started_at",
        "finished_at",
    )
    list_filter = ("status", "created_at", "started_at", "finished_at")
    search_fields = ("original_filename", "error")
    readonly_fields = (
        "source_file",
        "original_filename",
        "status",
        "summary",
        "error",
        "created_by",
        "created_at",
        "started_at",
        "finished_at",
    )

    def has_add_permission(self, request):
        return False
