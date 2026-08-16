from datetime import date, timedelta

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from core.analytics.models import NginxAnalyticsDashboard
from core.analytics.nginx_logs import AnalyticsLogError, get_report


@admin.register(NginxAnalyticsDashboard)
class NginxAnalyticsDashboardAdmin(admin.ModelAdmin):
    change_list_template = "admin/analytics/nginxanalyticsdashboard/change_list.html"

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("analytics.view_nginx_analytics")

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        return {"view": self.has_view_permission(request)}

    def add_view(self, request, form_url="", extra_context=None):
        raise PermissionDenied

    def change_view(self, request, object_id, form_url="", extra_context=None):
        raise PermissionDenied

    def delete_view(self, request, object_id, extra_context=None):
        raise PermissionDenied

    def history_view(self, request, object_id, extra_context=None):
        raise PermissionDenied

    @method_decorator(never_cache)
    def changelist_view(self, request, extra_context=None):
        if not self.has_view_permission(request):
            raise PermissionDenied

        today = timezone.localdate()
        default_start = today - timedelta(days=6)
        try:
            start = date.fromisoformat(request.GET.get("start", ""))
        except ValueError:
            start = default_start
        try:
            end = date.fromisoformat(request.GET.get("end", ""))
        except ValueError:
            end = today
        status_filter = request.GET.get("status", "all")
        report = None
        report_error = None
        try:
            report = get_report(start, end, status_filter)
        except AnalyticsLogError as exc:
            report_error = str(exc)

        context = {
            **self.admin_site.each_context(request),
            "title": "NGINX analytics",
            "opts": self.model._meta,
            "has_view_permission": True,
            "report": report,
            "report_error": report_error,
            "filters": {"start": start, "end": end, "status": status_filter},
            "status_choices": (
                ("all", "All statuses"),
                ("2xx", "2xx success"),
                ("3xx", "3xx redirect"),
                ("4xx", "4xx client error"),
                ("5xx", "5xx server error"),
            ),
            **(extra_context or {}),
        }
        return TemplateResponse(request, self.change_list_template, context)
