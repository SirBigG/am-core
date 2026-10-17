from functools import wraps

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.cache import add_never_cache_headers, patch_vary_headers
from django.views.decorators.http import require_safe
from mptt.admin import DraggableMPTTAdmin

from core.classifier.models import Area, Category, CategoryAIProfile, Country, Location, Region
from core.posts.guide_admin_permissions import guide_placements_in_category_trees, require_guide_placement_deletion
from core.posts.guide_hub import build_guide_hub_context, get_public_guide_sections
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.posts.templatetags.post_extras import full_url


class CategoryAIProfileInline(admin.StackedInline):
    model = CategoryAIProfile
    extra = 0
    max_num = 1
    fields = (
        "title",
        "status",
        "is_ai_enabled",
        "content",
        "recommendation_rules",
        "sources",
        "internal_notes",
        "updated_by",
        "updated",
    )
    readonly_fields = ("updated_by", "updated")


class GuideSectionInline(admin.TabularInline):
    model = GuideSection
    extra = 0
    fields = ("title", "description", "sort_order", "is_active")
    ordering = ("sort_order", "pk")
    show_change_link = True

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and request.user.has_perm("posts.delete_guidesectionarticle")


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin, admin.ModelAdmin):
    change_form_template = "admin/guide_hub_change_form.html"
    list_display = ("tree_actions", "indented_title", "slug", "is_active", "is_diary_species_parent")
    list_filter = ("is_active", "is_diary_species_parent", "is_for_user")
    search_fields = ["value", "slug"]
    inlines = (CategoryAIProfileInline, GuideSectionInline)

    def has_guide_preview_permission(self, request, obj=None):
        section_admin = self.admin_site.get_model_admin(GuideSection)
        post_admin = self.admin_site.get_model_admin(Post)
        return (
            self.has_view_permission(request, obj)
            and section_admin.has_view_permission(request)
            and (
                request.user.has_perm("posts.view_guidesectionarticle")
                or request.user.has_perm("posts.change_guidesectionarticle")
            )
            and post_admin.has_view_permission(request)
        )

    def get_guide_preview_url(self, request, obj):
        if obj is not None and obj.parent_id and self.has_guide_preview_permission(request, obj):
            return reverse(f"{self.admin_site.name}:classifier_category_guide_preview", args=[obj.pk])
        return None

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        context["guide_preview_url"] = self.get_guide_preview_url(request, obj)
        return super().render_change_form(request, context, add, change, form_url, obj)

    def get_urls(self):
        protected_preview = self.admin_site.admin_view(require_safe(self.guide_preview))

        @wraps(self.guide_preview)
        def preview(request, *args, **kwargs):
            response = protected_preview(request, *args, **kwargs)
            # Include login redirects and explicit 403/404/405 responses, too.
            add_never_cache_headers(response)
            patch_vary_headers(response, ("Cookie",))
            response["X-Robots-Tag"] = "noindex, nofollow"
            return response

        return [
            path("<path:object_id>/guide-preview/", preview, name="classifier_category_guide_preview"),
        ] + super().get_urls()

    def guide_preview(self, request, object_id):
        if not self.has_guide_preview_permission(request):
            return HttpResponseForbidden()
        category = self.get_object(request, object_id)
        if category is None or not category.parent_id:
            return HttpResponseNotFound()
        if not self.has_guide_preview_permission(request, category):
            return HttpResponseForbidden()
        sections = get_public_guide_sections(category.pk)
        post_ids = {article.post_id for section in sections for article in section.public_articles}
        visible_posts = self.admin_site.get_model_admin(Post).get_queryset(request).filter(pk__in=post_ids)
        if visible_posts.count() != len(post_ids):
            return HttpResponseForbidden()
        context = {
            **build_guide_hub_context(category, sections),
            "is_guide_preview": True,
            "guide_canonical_url": full_url(
                reverse(
                    "posts-list-view",
                    kwargs={
                        "parent": category.parent.slug,
                        "child": category.slug,
                    },
                )
            ),
            "guide_admin_url": reverse(f"{self.admin_site.name}:classifier_category_change", args=[category.pk]),
            "enable_analytics": False,
            "enable_adverts": False,
            "enable_internal_adverts": False,
        }
        return TemplateResponse(request, "posts/guide_hub.html", context)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        deleted_sections = [obj for obj in formset.deleted_objects if isinstance(obj, GuideSection)]
        for section in deleted_sections:
            if not self.admin_site.get_model_admin(GuideSection).has_delete_permission(request, section):
                raise PermissionDenied
        require_guide_placement_deletion(
            self.admin_site, request, GuideSectionArticle.objects.filter(section__in=deleted_sections)
        )
        for obj in instances:
            if isinstance(obj, CategoryAIProfile):
                obj.updated_by = request.user
            obj.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()

    def get_deleted_objects(self, objs, request):
        require_guide_placement_deletion(self.admin_site, request, guide_placements_in_category_trees(objs))
        return super().get_deleted_objects(objs, request)

    def delete_selected_tree(self, modeladmin, request, queryset):
        if request.POST.get("post"):
            # MPTT's confirmed action skips Django's related-object preflight.
            # Recheck on POST, including a forged or stale confirmation.
            _, _, permissions_needed, protected = self.get_deleted_objects(queryset, request)
            if permissions_needed or protected:
                raise PermissionDenied
        return super().delete_selected_tree(modeladmin, request, queryset)


@admin.register(CategoryAIProfile)
class CategoryAIProfileAdmin(admin.ModelAdmin):
    list_display = ("category", "title", "status", "is_ai_enabled", "updated")
    list_filter = ("status", "is_ai_enabled", "category__is_active", "category__is_diary_species_parent")
    search_fields = ("category__value", "category__slug", "title", "content", "recommendation_rules")
    autocomplete_fields = ("category",)
    readonly_fields = ("created", "updated", "updated_by")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "category",
                    "title",
                    "status",
                    "is_ai_enabled",
                    "content",
                    "recommendation_rules",
                    "sources",
                    "internal_notes",
                )
            },
        ),
        ("Audit", {"fields": ("updated_by", "created", "updated")}),
    )

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("value", "longitude", "latitude", "region", "area")
    list_filter = ("region", "area")
    search_fields = ("value",)


admin.site.register(Country)
admin.site.register(Region)
admin.site.register(Area)
