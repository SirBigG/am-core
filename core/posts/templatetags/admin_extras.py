from django import template

from core.posts.templatetags.admin_dashboard import get_admin_dashboard_metrics

register = template.Library()


@register.simple_tag(takes_context=True)
def admin_dashboard_metrics(context):
    request = context["request"]
    if not hasattr(request, "_admin_dashboard_metrics"):
        request._admin_dashboard_metrics = get_admin_dashboard_metrics(request.user)
    return request._admin_dashboard_metrics
