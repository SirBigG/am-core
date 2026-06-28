from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from core.adverts.models import Advert
from core.posts.models import Post, UsefulStatistic
from core.services.models import Feedback

DASHBOARD_PERIOD_DAYS = 30
LATEST_FEEDBACK_LIMIT = 5


def _admin_changelist_url(model):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")


def _admin_change_url(obj):
    return reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=(obj.pk,))


def _can_view(user, permission):
    return user.is_active and user.is_staff and user.has_perm(permission)


def get_admin_dashboard_metrics(user, now=None):
    now = now or timezone.now()
    since = now - timedelta(days=DASHBOARD_PERIOD_DAYS)
    cards = []
    feedback_items = []
    feedback_count = None

    if _can_view(user, "adverts.view_advert"):
        new_adverts = Advert.objects.filter(created__gte=since)
        cards.append(
            {
                "label": "Adverts",
                "value": new_adverts.count(),
                "description": (
                    f"{new_adverts.filter(is_active=True).count()} active, "
                    f"{new_adverts.filter(is_active=False).count()} inactive"
                ),
                "url": _admin_changelist_url(Advert),
            }
        )

    if _can_view(user, "posts.view_post"):
        new_posts = Post.objects.filter(publish_date__gte=since)
        cards.append(
            {
                "label": "Posts",
                "value": new_posts.count(),
                "description": (
                    f"{new_posts.filter(status=True).count()} published, "
                    f"{new_posts.filter(status=False).count()} unpublished"
                ),
                "url": _admin_changelist_url(Post),
            }
        )

    if _can_view(user, "pro_auth.view_user"):
        user_model = get_user_model()
        new_users = user_model.objects.filter(date_joined__gte=since)
        cards.append(
            {
                "label": "Users",
                "value": new_users.count(),
                "description": f"{new_users.filter(is_active=True).count()} active accounts joined",
                "url": _admin_changelist_url(user_model),
            }
        )

    if _can_view(user, "services.view_feedback"):
        recent_feedback = Feedback.objects.filter(created__gte=since)
        latest_feedback = recent_feedback.order_by("-created")[:LATEST_FEEDBACK_LIMIT]
        feedback_count = recent_feedback.count()
        feedback_items = [
            {
                "title": feedback.title,
                "email": feedback.email,
                "text": feedback.text,
                "created": feedback.created,
                "url": _admin_change_url(feedback),
            }
            for feedback in latest_feedback
        ]

    if _can_view(user, "posts.view_usefulstatistic"):
        new_useful_votes = UsefulStatistic.objects.filter(created__gte=since)
        cards.append(
            {
                "label": "Useful votes",
                "value": new_useful_votes.count(),
                "description": (
                    f"{new_useful_votes.filter(is_useful=True).count()} useful, "
                    f"{new_useful_votes.filter(is_useful=False).count()} not useful"
                ),
                "url": _admin_changelist_url(UsefulStatistic),
            }
        )

    return {
        "period_days": DASHBOARD_PERIOD_DAYS,
        "since": since,
        "cards": cards,
        "feedback_count": feedback_count,
        "feedback_items": feedback_items,
    }
