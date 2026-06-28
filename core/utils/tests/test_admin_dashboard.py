from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.adverts.models import Advert
from core.posts.models import Post
from core.posts.templatetags.admin_dashboard import DASHBOARD_PERIOD_DAYS, get_admin_dashboard_metrics
from core.services.models import Feedback
from core.utils.tests.factories import FeedbackFactory, PostFactory, StaffUserFactory, UserFactory


class AdminDashboardMetricsTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.since = self.now - timedelta(days=30)
        self.staff_user = StaffUserFactory(is_superuser=True)
        self.staff_user.date_joined = self.since - timedelta(days=1)
        self.staff_user.save(update_fields=["date_joined"])

    def test_metrics_count_last_30_days(self):
        recent_advert = Advert.objects.create(title="Recent advert", description="recent", contact="contact")
        old_advert = Advert.objects.create(title="Old advert", description="old", contact="contact")
        Advert.objects.filter(pk=recent_advert.pk).update(created=self.since + timedelta(days=1), is_active=True)
        Advert.objects.filter(pk=old_advert.pk).update(created=self.since - timedelta(seconds=1), is_active=True)

        recent_post = PostFactory(title="Recent post", publisher=self.staff_user)
        old_post = PostFactory(title="Old post", publisher=self.staff_user)
        Post.objects.filter(pk=recent_post.pk).update(publish_date=self.since + timedelta(days=1), status=True)
        Post.objects.filter(pk=old_post.pk).update(publish_date=self.since - timedelta(seconds=1), status=True)

        recent_user = UserFactory()
        old_user = UserFactory()
        recent_user.date_joined = self.since + timedelta(days=1)
        recent_user.save(update_fields=["date_joined"])
        old_user.date_joined = self.since - timedelta(seconds=1)
        old_user.save(update_fields=["date_joined"])

        recent_feedback = FeedbackFactory(title="Recent feedback", text="Recent issue description")
        old_feedback = FeedbackFactory(title="Old feedback", text="Old issue description")
        Feedback.objects.filter(pk=recent_feedback.pk).update(created=self.since + timedelta(days=1))
        Feedback.objects.filter(pk=old_feedback.pk).update(created=self.since - timedelta(seconds=1))

        dashboard = get_admin_dashboard_metrics(self.staff_user, now=self.now)

        self.assertEqual([card["value"] for card in dashboard["cards"]], [1, 1, 1])
        self.assertEqual(dashboard["feedback_count"], 1)
        self.assertEqual([feedback["title"] for feedback in dashboard["feedback_items"]], ["Recent feedback"])

    def test_metrics_respect_view_permissions(self):
        staff_user = StaffUserFactory()
        staff_user.user_permissions.add(Permission.objects.get(codename="view_feedback"))
        FeedbackFactory(title="Visible feedback")

        dashboard = get_admin_dashboard_metrics(staff_user, now=self.now)

        self.assertEqual(dashboard["cards"], [])
        self.assertEqual(dashboard["feedback_count"], 1)
        self.assertEqual(dashboard["feedback_items"][0]["title"], "Visible feedback")


class AdminDashboardIndexTests(TestCase):
    def test_admin_index_renders_metrics_and_latest_feedback(self):
        Site.objects.update_or_create(
            id=1,
            defaults={"domain": "localhost:8000", "name": "localhost"},
        )
        staff_user = StaffUserFactory(is_superuser=True)
        self.client.force_login(staff_user)

        Advert.objects.create(title="Admin advert", description="recent", contact="contact")
        PostFactory(title="Admin post")
        UserFactory(email="new-user@example.com")
        FeedbackFactory(title="Seed question", text="How do I add apple variety details?", email="farmer@example.com")

        response = self.client.get(reverse("admin:index"), headers={"host": "localhost:8000"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/index.html")
        self.assertContains(response, "Last 30 days")
        self.assertContains(response, "Adverts")
        self.assertContains(response, "Posts")
        self.assertContains(response, "Users")
        self.assertContains(response, "Latest feedback")
        self.assertContains(response, "Seed question")
        self.assertContains(response, "How do I add apple variety details?")
        self.assertContains(response, "admin/agromega-dashboard.css")

    def test_admin_index_reuses_dashboard_metrics_for_content_and_sidebar(self):
        Site.objects.update_or_create(
            id=1,
            defaults={"domain": "localhost:8000", "name": "localhost"},
        )
        staff_user = StaffUserFactory(is_superuser=True)
        self.client.force_login(staff_user)
        dashboard = {
            "period_days": DASHBOARD_PERIOD_DAYS,
            "since": timezone.now() - timedelta(days=DASHBOARD_PERIOD_DAYS),
            "cards": [
                {
                    "label": "Adverts",
                    "value": 3,
                    "description": "3 active in the last 30 days",
                    "url": reverse("admin:adverts_advert_changelist"),
                }
            ],
            "feedback_count": 0,
            "feedback_items": [],
        }

        with patch(
            "core.posts.templatetags.admin_extras.get_admin_dashboard_metrics", return_value=dashboard
        ) as metrics:
            response = self.client.get(reverse("admin:index"), headers={"host": "localhost:8000"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Adverts")
        self.assertContains(response, "Latest feedback (0)")
        metrics.assert_called_once_with(staff_user)
