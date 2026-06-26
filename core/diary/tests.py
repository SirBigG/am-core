from datetime import timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from core.classifier.models import Category, CategoryAIProfile
from core.diary.forms import (
    PLANT_BLOCKED_TEXT,
    DiaryForm,
    DiaryItemForm,
    PlantAttachmentFormSet,
    save_diary_plants,
)
from core.diary.models import (
    DIARY_ITEM_ACTION_CHOICES,
    Diary,
    DiaryItem,
    Planner,
    PlannerArea,
    PlannerPlanting,
    PlannerTask,
    Plant,
)
from core.diary.planner import extract_planner_spacing_guidance
from core.diary.recommendations import (
    PlantRecommendationService,
    buildPlantKnowledgeContext,
    buildPlantRecommendationSystemPrompt,
    buildPlantRecommendationUserPrompt,
    parsePlantRecommendationRules,
    preparePlantRecommendationPayload,
    selectRelevantRecommendationRules,
)
from core.utils.tests.factories import UserFactory


class DiaryOrderingTests(TestCase):
    def test_diary_items_order_by_latest_date_and_creation(self):
        user = UserFactory()
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        old_item = DiaryItem.objects.create(diary=diary, action_type="note", date="2026-04-25")
        first_today = DiaryItem.objects.create(diary=diary, action_type="watering", date="2026-04-26")
        latest_today = DiaryItem.objects.create(diary=diary, action_type="photo", date="2026-04-26")

        self.assertEqual(
            list(diary.diary_items.all()),
            [latest_today, first_today, old_item],
        )

    def test_diary_item_exposes_plain_action_label(self):
        user = UserFactory()
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        item = DiaryItem.objects.create(diary=diary, action_type="watering", date="2026-04-26")

        self.assertEqual(item.action_icon, "💧")
        self.assertEqual(item.action_label, "Підлив")

    def test_profile_diary_list_orders_by_updated(self):
        user = UserFactory()
        older_diary = Diary.objects.create(
            user=user,
            title="Older",
            description="desc",
            updated=timezone.now(),
        )
        newer_diary = Diary.objects.create(
            user=user,
            title="Newer",
            description="desc",
            updated=timezone.now(),
        )
        Diary.objects.filter(pk=older_diary.pk).update(updated=timezone.datetime(2026, 4, 24, tzinfo=dt_timezone.utc))
        Diary.objects.filter(pk=newer_diary.pk).update(updated=timezone.datetime(2026, 4, 25, tzinfo=dt_timezone.utc))

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-list"))

        self.assertEqual(list(response.context["object_list"]), [newer_diary, older_diary])

    def test_add_diary_form_has_back_link(self):
        user = UserFactory()

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Назад до щоденників")
        self.assertContains(response, reverse("pro_auth:profile-diary-list"))

    def test_update_diary_form_has_back_link(self):
        user = UserFactory()
        diary = Diary.objects.create(user=user, title="Diary", description="desc")

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-update", kwargs={"pk": diary.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Назад до історії")
        self.assertContains(response, diary.get_profile_absolute_url())

    def test_profile_diary_list_prefetches_latest_event(self):
        user = UserFactory()
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        old_item = DiaryItem.objects.create(diary=diary, action_type="note", date="2026-04-25")
        latest_item = DiaryItem.objects.create(diary=diary, action_type="photo", date="2026-04-26")

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-list"))
        listed_diary = response.context["object_list"][0]
        latest_item.refresh_from_db()

        self.assertEqual(listed_diary.latest_diary_items[0], latest_item)
        self.assertEqual(listed_diary.latest_diary_items[1], old_item)
        self.assertEqual(listed_diary.last_diary_item, latest_item)
        self.assertEqual(listed_diary.diary_items_count, 2)
        self.assertContains(response, date_format(latest_item.date, "j F Y"))

    def test_profile_diary_list_summary_uses_active_plants_only(self):
        user = UserFactory()
        category = Category.objects.create(slug="basil", value="Базилік")
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        active_plant = Plant.objects.create(user=user, category=category, variety="Genovese")
        completed_plant = Plant.objects.create(
            user=user,
            category=category,
            variety="Purple",
            status="completed",
        )
        diary.plants.set([active_plant, completed_plant])

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-list"))
        listed_diary = response.context["object_list"][0]

        self.assertEqual(listed_diary.plant_summary, active_plant.display_name)

    def test_profile_diary_list_builds_dashboard_context(self):
        user = UserFactory()
        today = timezone.localdate()
        category = Category.objects.create(slug="dill", value="Кріп")
        diary = Diary.objects.create(user=user, title="Garden", description="desc")
        first_plant = Plant.objects.create(user=user, category=category, variety="Mammoth")
        second_plant = Plant.objects.create(user=user, category=category, variety="Bouquet")
        third_plant = Plant.objects.create(user=user, category=category, variety="Fernleaf")
        diary.plants.set([first_plant, second_plant, third_plant])
        archived_diary = Diary.objects.create(user=user, title="Archived", description="desc", is_archived=True)
        archived_plant = Plant.objects.create(user=user, category=category, variety="Old")
        archived_diary.plants.add(archived_plant)

        old_watering = DiaryItem.objects.create(
            diary=diary,
            action_type="watering",
            date=today - timedelta(days=4),
        )
        old_watering.plants.add(first_plant)
        harvest = DiaryItem.objects.create(
            diary=diary,
            action_type="harvest",
            harvest_amount="1.20",
            harvest_unit="kg",
            date=today,
        )
        harvest.plants.add(first_plant)
        note = DiaryItem.objects.create(diary=diary, action_type="note", date=today - timedelta(days=1))
        note.plants.add(second_plant)
        archived_harvest = DiaryItem.objects.create(
            diary=archived_diary,
            action_type="harvest",
            harvest_amount="99.00",
            harvest_unit="kg",
            date=today,
        )
        archived_harvest.plants.add(archived_plant)

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-list"))
        dashboard = response.context["diary_dashboard"]

        self.assertEqual(dashboard["active_plants_count"], 3)
        self.assertEqual(dashboard["weekly_actions_count"], 3)
        self.assertEqual(dashboard["last_watering"], old_watering)
        self.assertEqual(dashboard["harvest_summary"][0]["display"], "1.2 кг")
        self.assertEqual(dashboard["last_harvest"], harvest)
        self.assertEqual(dashboard["attention_count"], 3)
        self.assertEqual(dashboard["plants_without_actions_count"], 1)
        self.assertEqual(dashboard["plants_without_actions"], [third_plant])
        self.assertEqual(dashboard["history_days_count"], 5)
        self.assertEqual(dashboard["oldest_item_date"], today - timedelta(days=4))
        self.assertEqual(dashboard["most_active_diary"], diary)
        self.assertEqual(dashboard["most_active_actions_count"], 3)
        listed_diary = response.context["active_diaries"][0]
        self.assertTrue(listed_diary.needs_attention)
        self.assertEqual(response.context["attention_diaries"], [listed_diary])

    def test_profile_diary_dashboard_links_active_plants_card(self):
        user = UserFactory()
        self.client.force_login(user)

        response = self.client.get(reverse("pro_auth:profile-diary-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("pro_auth:profile-plant-list"))
        self.assertContains(response, "Переглянути всі рослини")

    def test_profile_plant_list_contains_only_current_user_plants_and_full_context(self):
        user = UserFactory()
        other_user = UserFactory()
        today = timezone.localdate()
        category = Category.objects.create(slug="cucumber", value="Огірок")
        diary = Diary.objects.create(user=user, title="Теплиця", description="desc")
        active_plant = Plant.objects.create(
            user=user,
            category=category,
            variety="Артист F1",
            title="Лівий ряд",
            description="Перший огірок сезону",
            plant_date=today - timedelta(days=20),
        )
        completed_plant = Plant.objects.create(
            user=user,
            category=category,
            variety="Кураж",
            plant_date=today - timedelta(days=40),
            status="completed",
            completed_at=today - timedelta(days=5),
        )
        Plant.objects.create(user=other_user, category=category, variety="Чужа рослина")
        diary.plants.set([active_plant, completed_plant])
        old_action = DiaryItem.objects.create(
            diary=diary,
            action_type="watering",
            date=today - timedelta(days=2),
        )
        old_action.plants.add(active_plant)
        latest_action = DiaryItem.objects.create(
            diary=diary,
            action_type="note",
            description="З'явилася нова зав'язь",
            date=today - timedelta(days=1),
        )
        latest_action.plants.add(active_plant)

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-plant-list"))

        self.assertEqual(response.status_code, 200)
        listed_plants = response.context["plants"]
        self.assertEqual([plant.pk for plant in listed_plants], [active_plant.pk, completed_plant.pk])
        listed_active = listed_plants[0]
        listed_completed = listed_plants[1]
        self.assertEqual(listed_active.age_days, 20)
        self.assertEqual(listed_active.diary_items_count, 2)
        self.assertEqual(listed_active.latest_diary_item, latest_action)
        self.assertEqual(listed_active.profile_diaries, [diary])
        self.assertEqual(listed_completed.age_days, 35)
        self.assertEqual(response.context["active_plants"], [listed_active])
        self.assertEqual(response.context["completed_plants"], [listed_completed])
        self.assertContains(response, "Артист F1")
        self.assertContains(response, "нова зав")
        self.assertNotContains(response, "Чужа рослина")

    def test_profile_diary_list_renders_diary_view_tabs(self):
        user = UserFactory()
        category = Category.objects.create(slug="basil", value="Базилік")
        active_diary = Diary.objects.create(user=user, title="Active", description="desc")
        attention_plant = Plant.objects.create(user=user, category=category, variety="Genovese")
        active_diary.plants.add(attention_plant)
        archived_diary = Diary.objects.create(
            user=user,
            title="Archived",
            description="desc",
            is_archived=True,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-list"))

        self.assertContains(response, 'data-diary-view-tab="all"')
        self.assertContains(response, 'data-diary-view-tab="attention"')
        self.assertContains(response, 'data-diary-view-tab="archive"')
        self.assertContains(response, 'data-diary-view-groups="all attention"')
        self.assertContains(response, 'data-diary-view-groups="archive"')
        self.assertNotContains(response, "profile-diary-card profile-diary-card--large")
        self.assertIn(active_diary, response.context["attention_diaries"])
        self.assertIn(archived_diary, response.context["archived_diaries"])

    def test_profile_diary_list_renders_add_action_modal(self):
        user = UserFactory()
        category = Category.objects.create(slug="basil", value="Базилік")
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        plant = Plant.objects.create(user=user, category=category, variety="Genovese")
        diary.plants.add(plant)

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-list"))

        self.assertContains(response, "+ Додати іншу дію")
        self.assertContains(response, f'id="diaryCardActionModal{diary.pk}"')
        self.assertContains(response, f'name="_form_prefix" value="diary-{diary.pk}"')
        self.assertContains(
            response,
            f'name="next" value="{reverse("pro_auth:profile-diary-list")}"',
        )

    def test_prefixed_diary_item_form_from_list_creates_item(self):
        user = UserFactory()
        category = Category.objects.create(slug="basil", value="Базилік")
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        plant = Plant.objects.create(user=user, category=category, variety="Genovese")
        diary.plants.add(plant)
        prefix = f"diary-{diary.pk}"

        self.client.force_login(user)
        response = self.client.post(
            reverse("pro_auth:profile-diary-item-add", kwargs={"diary_id": diary.pk}),
            {
                "next": reverse("pro_auth:profile-diary-list"),
                "_form_prefix": prefix,
                f"{prefix}-action_type": "note",
                f"{prefix}-apply_to_all": "on",
                f"{prefix}-description": "Підживлення після огляду",
                f"{prefix}-date": "2026-05-25",
            },
        )

        self.assertRedirects(
            response,
            reverse("pro_auth:profile-diary-list"),
            fetch_redirect_response=False,
        )
        item = DiaryItem.objects.get(diary=diary, action_type="note")
        self.assertEqual(item.description, "Підживлення після огляду")
        self.assertTrue(item.apply_to_all)

    def test_profile_diary_list_splits_active_and_archived_diaries(self):
        user = UserFactory()
        active_diary = Diary.objects.create(user=user, title="Active", description="desc", is_archived=False)
        archived_diary = Diary.objects.create(user=user, title="Archived", description="desc", is_archived=True)

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-list"))

        self.assertIn(active_diary, response.context["active_diaries"])
        self.assertNotIn(active_diary, response.context["archived_diaries"])
        self.assertIn(archived_diary, response.context["archived_diaries"])
        self.assertNotIn(archived_diary, response.context["active_diaries"])

    def test_profile_diary_list_renders_empty_onboarding_state(self):
        user = UserFactory()

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-list"))

        self.assertContains(response, "Як почати")
        self.assertContains(response, "Створи щоденник для грядки")
        self.assertContains(response, "profile-diary-onboarding")

    def test_archived_diaries_are_hidden_from_public_list_and_detail(self):
        user = UserFactory()
        public_archived = Diary.objects.create(
            user=user,
            title="Archived public",
            description="desc",
            public=True,
            is_archived=True,
        )
        public_active = Diary.objects.create(
            user=user,
            title="Active public",
            description="desc",
            public=True,
            is_archived=False,
        )

        list_response = self.client.get(reverse("diaries:list"))
        detail_response = self.client.get(reverse("diaries:detail", kwargs={"pk": public_archived.pk}))

        self.assertEqual(list_response.status_code, 200)
        self.assertIn(public_active, list_response.context["object_list"])
        self.assertNotIn(public_archived, list_response.context["object_list"])
        self.assertEqual(detail_response.status_code, 404)

    def test_archive_and_restore_diary_are_soft_actions(self):
        user = UserFactory()
        diary = Diary.objects.create(user=user, title="Diary", description="desc", is_archived=False)

        self.client.force_login(user)
        archive_response = self.client.get(reverse("pro_auth:profile-diary-delete", kwargs={"pk": diary.pk}))
        diary.refresh_from_db()

        self.assertEqual(archive_response.status_code, 302)
        self.assertTrue(diary.is_archived)
        self.assertTrue(Diary.objects.filter(pk=diary.pk).exists())

        restore_response = self.client.get(reverse("pro_auth:profile-diary-restore", kwargs={"pk": diary.pk}))
        diary.refresh_from_db()

        self.assertEqual(restore_response.status_code, 302)
        self.assertFalse(diary.is_archived)

    def test_quick_watering_creates_item_for_all_active_plants(self):
        user = UserFactory()
        category = Category.objects.create(slug="basil", value="Базилік")
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        active_plant = Plant.objects.create(user=user, category=category, variety="Genovese")
        completed_plant = Plant.objects.create(user=user, category=category, variety="Purple", status="completed")
        diary.plants.set([active_plant, completed_plant])

        self.client.force_login(user)
        response = self.client.post(
            reverse("pro_auth:profile-diary-quick-watering", kwargs={"pk": diary.pk}),
            {"apply_to_all": "1"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("quick_action=watering_added", response["Location"])
        item = DiaryItem.objects.get(diary=diary, action_type="watering")
        self.assertTrue(item.apply_to_all)
        self.assertEqual(list(item.plants.all()), [active_plant])

    def test_quick_watering_creates_item_for_selected_plants(self):
        user = UserFactory()
        category = Category.objects.create(slug="basil", value="Базилік")
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        first_plant = Plant.objects.create(user=user, category=category, variety="Genovese")
        second_plant = Plant.objects.create(user=user, category=category, variety="Thai")
        diary.plants.set([first_plant, second_plant])

        self.client.force_login(user)
        response = self.client.post(
            reverse("pro_auth:profile-diary-quick-watering", kwargs={"pk": diary.pk}),
            {"apply_to_all": "0", "plants": [str(second_plant.pk)]},
        )

        self.assertEqual(response.status_code, 302)
        item = DiaryItem.objects.get(diary=diary, action_type="watering")
        self.assertFalse(item.apply_to_all)
        self.assertEqual(list(item.plants.all()), [second_plant])

    def test_quick_watering_redirects_to_safe_next_url(self):
        user = UserFactory()
        category = Category.objects.create(slug="basil", value="Базилік")
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        plant = Plant.objects.create(user=user, category=category, variety="Genovese")
        diary.plants.add(plant)
        next_url = diary.get_profile_absolute_url()

        self.client.force_login(user)
        response = self.client.post(
            reverse("pro_auth:profile-diary-quick-watering", kwargs={"pk": diary.pk}),
            {"apply_to_all": "1", "next": next_url},
        )

        self.assertRedirects(
            response,
            f"{next_url}?quick_action=watering_added",
            fetch_redirect_response=False,
        )

    def test_quick_watering_ignores_external_next_url(self):
        user = UserFactory()
        category = Category.objects.create(slug="basil", value="Базилік")
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        plant = Plant.objects.create(user=user, category=category, variety="Genovese")
        diary.plants.add(plant)

        self.client.force_login(user)
        response = self.client.post(
            reverse("pro_auth:profile-diary-quick-watering", kwargs={"pk": diary.pk}),
            {"apply_to_all": "1", "next": "https://example.com/profile/diary"},
        )

        self.assertRedirects(
            response,
            f"{reverse('pro_auth:profile-diary-list')}?quick_action=watering_added",
            fetch_redirect_response=False,
        )

    def test_quick_watering_requires_owned_diary(self):
        owner = UserFactory()
        other_user = UserFactory()
        diary = Diary.objects.create(user=owner, title="Diary", description="desc")

        self.client.force_login(other_user)
        response = self.client.post(
            reverse("pro_auth:profile-diary-quick-watering", kwargs={"pk": diary.pk}),
            {"apply_to_all": "1"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(DiaryItem.objects.filter(diary=diary, action_type="watering").exists())


class ProfilePlannerTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.client.force_login(self.user)

    def test_planner_page_asks_user_for_dimensions_before_creating_workspace(self):
        response = self.client.get(reverse("pro_auth:profile-planner"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Planner.objects.filter(user=self.user).exists())
        self.assertContains(response, "Мій планер")
        self.assertContains(response, "Створіть свою ділянку")
        self.assertContains(response, "Ширина, м")
        self.assertContains(response, "Довжина, м")
        self.assertContains(response, reverse("pro_auth:profile-planner"))

    def test_create_planner_uses_user_dimensions(self):
        response = self.client.post(
            reverse("pro_auth:profile-planner-create"),
            {
                "title": "Город біля дому",
                "width_m": "17.5",
                "height_m": "9.5",
                "grid_step_m": "0.25",
            },
        )

        planner = Planner.objects.get(user=self.user)
        self.assertRedirects(
            response,
            f'{reverse("pro_auth:profile-planner")}?planner={planner.pk}',
            fetch_redirect_response=False,
        )
        self.assertEqual(planner.title, "Город біля дому")
        self.assertEqual(planner.width_m, Decimal("17.50"))
        self.assertEqual(planner.height_m, Decimal("9.50"))
        self.assertEqual(planner.grid_step_m, Decimal("0.25"))

        page_response = self.client.get(reverse("pro_auth:profile-planner"))
        self.assertContains(page_response, 'data-width="17.50"')
        self.assertContains(page_response, 'data-height="9.50"')
        self.assertContains(page_response, 'data-grid-step="0.25"')

    def test_planner_pages_use_profile_sidebar_layout(self):
        planner = Planner.objects.create(user=self.user, title="Профільний план")

        planner_page = self.client.get(reverse("pro_auth:profile-planner"), {"planner": planner.pk})
        create_page = self.client.get(reverse("pro_auth:profile-planner-create"))

        self.assertContains(planner_page, "planner-profile-shell")
        self.assertContains(planner_page, "profile-sidebar-nav")
        self.assertContains(planner_page, "profile-sidebar-col")
        self.assertContains(planner_page, "Мій планер")

        self.assertContains(create_page, "profile-sidebar-nav")
        self.assertContains(create_page, "profile-sidebar-col")
        self.assertContains(create_page, "profile-content-col")
        self.assertContains(create_page, "Мій планер")

    def test_user_can_create_and_switch_between_multiple_plans(self):
        first = Planner.objects.create(user=self.user, title="Сезон 2026")

        create_page = self.client.get(reverse("pro_auth:profile-planner-create"))
        self.assertContains(create_page, "Створіть новий план")

        response = self.client.post(
            reverse("pro_auth:profile-planner-create"),
            {
                "title": "Сезон 2027",
                "width_m": "30",
                "height_m": "18",
                "grid_step_m": "0.5",
            },
        )
        second = Planner.objects.get(user=self.user, title="Сезон 2027")
        self.assertRedirects(
            response,
            f'{reverse("pro_auth:profile-planner")}?planner={second.pk}',
            fetch_redirect_response=False,
        )

        selected_page = self.client.get(
            reverse("pro_auth:profile-planner"),
            {"planner": first.pk},
        )
        self.assertEqual(selected_page.context["planner"], first)
        self.assertContains(selected_page, "Сезон 2026")
        self.assertContains(selected_page, "Сезон 2027")

    def test_delete_planner_only_allows_owned_empty_plan(self):
        empty_planner = Planner.objects.create(user=self.user, title="Порожній")
        response = self.client.post(
            reverse("pro_auth:profile-planner-delete", kwargs={"pk": empty_planner.pk})
        )
        self.assertRedirects(response, reverse("pro_auth:profile-planner"), fetch_redirect_response=False)
        self.assertFalse(Planner.objects.filter(pk=empty_planner.pk).exists())

        used_planner = Planner.objects.create(user=self.user, title="З грядкою")
        PlannerArea.objects.create(planner=used_planner, title="Грядка")
        response = self.client.post(
            reverse("pro_auth:profile-planner-delete", kwargs={"pk": used_planner.pk})
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Planner.objects.filter(pk=used_planner.pk).exists())

        task_planner = Planner.objects.create(user=self.user, title="Зі справою")
        PlannerTask.objects.create(planner=task_planner, title="Підготувати грядку")
        response = self.client.post(
            reverse("pro_auth:profile-planner-delete", kwargs={"pk": task_planner.pk})
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Planner.objects.filter(pk=task_planner.pk).exists())

        foreign_planner = Planner.objects.create(user=self.other_user, title="Чужий")
        response = self.client.post(
            reverse("pro_auth:profile-planner-delete", kwargs={"pk": foreign_planner.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_duplicate_planner_copies_layout_without_diaries_or_plantings(self):
        source = Planner.objects.create(
            user=self.user,
            title="Сезон 2026",
            width_m="28",
            height_m="16",
            grid_step_m="0.25",
        )
        diary = Diary.objects.create(user=self.user, title="Теплиця", description="desc")
        area = PlannerArea.objects.create(
            planner=source,
            diary=diary,
            title="Південна теплиця",
            area_type="greenhouse",
            color="#4fae91",
            x_m="3",
            y_m="4",
            width_m="8",
            height_m="5",
        )
        plant = Plant.objects.create(user=self.user, title="Огірки")
        PlannerPlanting.objects.create(area=area, plant=plant, mode="rows", rows=3)
        PlannerTask.objects.create(planner=source, area=area, title="Полити")

        response = self.client.post(
            reverse("pro_auth:profile-planner-duplicate", kwargs={"pk": source.pk}),
            {"title": "Сезон 2027"},
        )

        source.refresh_from_db()
        area.refresh_from_db()
        duplicate = Planner.objects.get(user=self.user, title="Сезон 2027")
        self.assertRedirects(
            response,
            f'{reverse("pro_auth:profile-planner")}?planner={duplicate.pk}',
            fetch_redirect_response=False,
        )
        self.assertEqual(duplicate.width_m, source.width_m)
        self.assertEqual(duplicate.height_m, source.height_m)
        self.assertEqual(duplicate.grid_step_m, source.grid_step_m)
        copied_area = duplicate.areas.get()
        self.assertEqual(copied_area.title, area.title)
        self.assertEqual(copied_area.area_type, area.area_type)
        self.assertEqual(copied_area.x_m, area.x_m)
        self.assertIsNone(copied_area.diary_id)
        self.assertFalse(copied_area.plantings.exists())
        self.assertFalse(duplicate.tasks.exists())
        self.assertTrue(PlannerPlanting.objects.filter(area=area, plant=plant).exists())

    def test_duplicate_planner_rejects_other_users_plan(self):
        foreign_planner = Planner.objects.create(user=self.other_user, title="Чужий")

        response = self.client.post(
            reverse("pro_auth:profile-planner-duplicate", kwargs={"pk": foreign_planner.pk}),
            {"title": "Копія"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Planner.objects.filter(user=self.user, title="Копія").exists())

    def test_planner_progress_reflects_real_layout_and_season_state(self):
        planner = Planner.objects.create(user=self.user, title="Сезон")

        response = self.client.get(reverse("pro_auth:profile-planner"), {"planner": planner.pk})
        self.assertEqual(response.context["planner_progress_percent"], 25)

        area = PlannerArea.objects.create(planner=planner, title="Грядка")
        plant = Plant.objects.create(user=self.user, title="Морква")
        planting = PlannerPlanting.objects.create(
            area=area,
            plant=plant,
            mode="rows",
            rows=4,
            status="planned",
        )
        response = self.client.get(reverse("pro_auth:profile-planner"), {"planner": planner.pk})
        self.assertEqual(response.context["planner_progress_percent"], 75)
        self.assertFalse(response.context["planner_progress_steps"][-1]["completed"])

        planting.status = "growing"
        planting.save(update_fields=["status"])
        response = self.client.get(reverse("pro_auth:profile-planner"), {"planner": planner.pk})
        self.assertEqual(response.context["planner_progress_percent"], 100)
        self.assertTrue(response.context["planner_progress_steps"][-1]["completed"])

    def test_planner_tasks_can_be_created_completed_and_deleted(self):
        planner = Planner.objects.create(user=self.user, title="Сезон")
        area = PlannerArea.objects.create(planner=planner, title="Теплиця")
        due_date = timezone.localdate() + timedelta(days=2)

        response = self.client.post(
            reverse("pro_auth:profile-planner-task-add", kwargs={"planner_pk": planner.pk}),
            {"title": "Підв’язати огірки", "due_date": due_date.isoformat(), "area_id": area.pk},
        )
        task = PlannerTask.objects.get(planner=planner)
        self.assertRedirects(
            response,
            f'{reverse("pro_auth:profile-planner")}?planner={planner.pk}',
            fetch_redirect_response=False,
        )
        self.assertEqual(task.title, "Підв’язати огірки")
        self.assertEqual(task.area, area)
        self.assertEqual(task.due_date, due_date)

        response = self.client.post(
            reverse("pro_auth:profile-planner-task-update", kwargs={"pk": task.pk}),
            {"title": "Підв’язати й оглянути", "due_date": "", "area_id": ""},
        )
        task.refresh_from_db()
        self.assertRedirects(
            response,
            f'{reverse("pro_auth:profile-planner")}?planner={planner.pk}',
            fetch_redirect_response=False,
        )
        self.assertEqual(task.title, "Підв’язати й оглянути")
        self.assertIsNone(task.area_id)
        self.assertIsNone(task.due_date)

        response = self.client.post(reverse("pro_auth:profile-planner-task-toggle", kwargs={"pk": task.pk}))
        task.refresh_from_db()
        self.assertRedirects(
            response,
            f'{reverse("pro_auth:profile-planner")}?planner={planner.pk}',
            fetch_redirect_response=False,
        )
        self.assertTrue(task.is_completed)
        self.assertIsNotNone(task.completed_at)

        self.client.post(reverse("pro_auth:profile-planner-task-toggle", kwargs={"pk": task.pk}))
        task.refresh_from_db()
        self.assertFalse(task.is_completed)
        self.assertIsNone(task.completed_at)

        response = self.client.post(reverse("pro_auth:profile-planner-task-delete", kwargs={"pk": task.pk}))
        self.assertRedirects(
            response,
            f'{reverse("pro_auth:profile-planner")}?planner={planner.pk}',
            fetch_redirect_response=False,
        )
        self.assertFalse(PlannerTask.objects.filter(pk=task.pk).exists())

    def test_planner_tasks_are_scoped_and_overdue_count_is_exposed(self):
        planner = Planner.objects.create(user=self.user, title="Сезон")
        foreign_planner = Planner.objects.create(user=self.other_user, title="Чужий сезон")
        foreign_area = PlannerArea.objects.create(planner=foreign_planner, title="Чужа грядка")

        response = self.client.post(
            reverse("pro_auth:profile-planner-task-add", kwargs={"planner_pk": planner.pk}),
            {"title": "Неправильна зона", "area_id": foreign_area.pk},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(PlannerTask.objects.filter(planner=planner).exists())

        task = PlannerTask.objects.create(
            planner=planner,
            title="Прострочена справа",
            due_date=timezone.localdate() - timedelta(days=1),
        )
        update_response = self.client.post(
            reverse("pro_auth:profile-planner-task-update", kwargs={"pk": task.pk}),
            {"title": "Спроба переносу", "area_id": foreign_area.pk},
        )
        self.assertEqual(update_response.status_code, 404)
        task.refresh_from_db()
        self.assertEqual(task.title, "Прострочена справа")
        self.assertIsNone(task.area_id)

        page = self.client.get(reverse("pro_auth:profile-planner"), {"planner": planner.pk})
        self.assertEqual(page.context["planner_open_tasks_count"], 1)
        self.assertEqual(page.context["planner_overdue_tasks_count"], 1)
        self.assertTrue(page.context["planner_tasks"][0].is_overdue)
        self.assertEqual(page.context["planner_tasks"][0].bucket, "overdue")
        self.assertEqual(page.context["planner_task_groups"][0]["label"], "Прострочено")
        self.assertEqual(page.context["planner_task_groups"][0]["tasks"], [task])

        toggle_response = self.client.post(
            reverse("pro_auth:profile-planner-task-toggle", kwargs={"pk": task.pk})
        )
        self.assertEqual(toggle_response.status_code, 302)

        foreign_task = PlannerTask.objects.create(planner=foreign_planner, title="Чужа справа")
        self.assertEqual(
            self.client.post(reverse("pro_auth:profile-planner-task-toggle", kwargs={"pk": foreign_task.pk})).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("pro_auth:profile-planner-task-delete", kwargs={"pk": foreign_task.pk})).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("pro_auth:profile-planner-task-update", kwargs={"pk": foreign_task.pk}),
                {"title": "Змінити"},
            ).status_code,
            404,
        )

    def test_planner_tasks_are_grouped_by_season_timing(self):
        planner = Planner.objects.create(user=self.user, title="План справ")
        today = timezone.localdate()
        PlannerTask.objects.create(planner=planner, title="Прострочена", due_date=today - timedelta(days=1))
        PlannerTask.objects.create(planner=planner, title="Сьогодні", due_date=today)
        PlannerTask.objects.create(planner=planner, title="Найближча", due_date=today + timedelta(days=2))
        PlannerTask.objects.create(planner=planner, title="Без дати")
        PlannerTask.objects.create(planner=planner, title="Готова", is_completed=True, due_date=today - timedelta(days=3))

        page = self.client.get(reverse("pro_auth:profile-planner"), {"planner": planner.pk})
        group_labels = [group["label"] for group in page.context["planner_task_groups"]]
        grouped_titles = [
            [task.title for task in group["tasks"]]
            for group in page.context["planner_task_groups"]
        ]

        self.assertEqual(group_labels, ["Прострочено", "Сьогодні", "Найближчі", "Без дати", "Виконані"])
        self.assertEqual(grouped_titles, [["Прострочена"], ["Сьогодні"], ["Найближча"], ["Без дати"], ["Готова"]])

    def test_planner_area_payload_includes_area_task_summary(self):
        planner = Planner.objects.create(user=self.user, title="План справ")
        area = PlannerArea.objects.create(planner=planner, title="Теплиця")
        today = timezone.localdate()
        PlannerTask.objects.create(planner=planner, area=area, title="Прострочена", due_date=today - timedelta(days=1))
        PlannerTask.objects.create(planner=planner, area=area, title="Найближча", due_date=today + timedelta(days=2))
        PlannerTask.objects.create(planner=planner, area=area, title="Готова", is_completed=True)
        PlannerTask.objects.create(planner=planner, title="Для всієї ділянки")

        page = self.client.get(reverse("pro_auth:profile-planner"), {"planner": planner.pk})
        area_payload = page.context["planner_areas_payload"][0]

        self.assertEqual(area_payload["tasks"]["openCount"], 2)
        self.assertEqual(area_payload["tasks"]["overdueCount"], 1)
        self.assertEqual(area_payload["tasks"]["nextTitle"], "Прострочена")
        self.assertEqual(area_payload["tasks"]["nextBucket"], "overdue")

    def test_planner_area_update_payload_keeps_area_task_summary(self):
        planner = Planner.objects.create(user=self.user, title="План справ")
        area = PlannerArea.objects.create(planner=planner, title="Теплиця")
        today = timezone.localdate()
        PlannerTask.objects.create(
            planner=planner,
            area=area,
            title="Прострочена",
            due_date=today - timedelta(days=1),
        )

        response = self.client.post(
            reverse("pro_auth:profile-planner-area-update", kwargs={"pk": area.pk}),
            {
                "x_m": "1",
                "y_m": "2",
                "width_m": "4",
                "height_m": "2",
            },
        )
        payload = response.json()["area"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["tasks"]["openCount"], 1)
        self.assertEqual(payload["tasks"]["overdueCount"], 1)
        self.assertEqual(payload["tasks"]["nextTitle"], "Прострочена")
        self.assertEqual(payload["tasks"]["nextBucket"], "overdue")

    def test_settings_update_user_dimensions_and_keep_areas_inside_canvas(self):
        planner = Planner.objects.create(user=self.user, width_m="20", height_m="12")
        area = PlannerArea.objects.create(
            planner=planner,
            title="Крайня грядка",
            x_m="15",
            y_m="8",
            width_m="4",
            height_m="3",
        )

        response = self.client.post(
            reverse("pro_auth:profile-planner-settings", kwargs={"pk": planner.pk}),
            {
                "title": "Менший город",
                "width_m": "10",
                "height_m": "7",
                "grid_step_m": "0.5",
            },
        )

        self.assertRedirects(
            response,
            f'{reverse("pro_auth:profile-planner")}?planner={planner.pk}',
            fetch_redirect_response=False,
        )
        planner.refresh_from_db()
        area.refresh_from_db()
        self.assertEqual(planner.width_m, Decimal("10.00"))
        self.assertEqual(planner.height_m, Decimal("7.00"))
        self.assertEqual(area.x_m, Decimal("6.00"))
        self.assertEqual(area.y_m, Decimal("4.00"))

    def test_planner_page_only_exposes_current_user_areas(self):
        planner = Planner.objects.create(user=self.user, title="Моя ділянка")
        own_area = PlannerArea.objects.create(planner=planner, title="Моя грядка")
        other_planner = Planner.objects.create(user=self.other_user, title="Чужа ділянка")
        PlannerArea.objects.create(planner=other_planner, title="Чужа грядка")

        response = self.client.get(reverse("pro_auth:profile-planner"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["planner_areas"], [own_area])
        self.assertEqual(
            [area["title"] for area in response.context["planner_areas_payload"]],
            ["Моя грядка"],
        )

    def test_create_area_can_link_existing_diary(self):
        planner = Planner.objects.create(user=self.user, title="Моя ділянка", width_m="12", height_m="8")
        diary = Diary.objects.create(user=self.user, title="Теплиця", description="desc")

        response = self.client.post(
            reverse("pro_auth:profile-planner-area-add", kwargs={"planner_pk": planner.pk}),
            {
                "title": "Теплиця біля дому",
                "area_type": "greenhouse",
                "width_m": "6",
                "height_m": "3",
                "diary_id": diary.pk,
            },
        )

        self.assertEqual(response.status_code, 201)
        area = PlannerArea.objects.get(planner=planner)
        self.assertEqual(area.diary, diary)
        self.assertEqual(area.area_type, "greenhouse")
        self.assertEqual(response.json()["area"]["diaryTitle"], diary.title)

    def test_update_area_clamps_geometry_to_planner_bounds(self):
        planner = Planner.objects.create(user=self.user, width_m="10", height_m="6")
        area = PlannerArea.objects.create(planner=planner, title="Грядка", width_m="4", height_m="2")

        response = self.client.post(
            reverse("pro_auth:profile-planner-area-update", kwargs={"pk": area.pk}),
            {"x_m": "9", "y_m": "5", "width_m": "5", "height_m": "3"},
        )

        self.assertEqual(response.status_code, 200)
        area.refresh_from_db()
        self.assertEqual(area.x_m, 5)
        self.assertEqual(area.y_m, 3)
        self.assertEqual(area.width_m, 5)
        self.assertEqual(area.height_m, 3)

    def test_area_endpoints_reject_other_users(self):
        other_planner = Planner.objects.create(user=self.other_user)
        other_area = PlannerArea.objects.create(planner=other_planner, title="Чужа грядка")

        update_response = self.client.post(
            reverse("pro_auth:profile-planner-area-update", kwargs={"pk": other_area.pk}),
            {"x_m": "1"},
        )
        delete_response = self.client.post(
            reverse("pro_auth:profile-planner-area-delete", kwargs={"pk": other_area.pk})
        )

        self.assertEqual(update_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(PlannerArea.objects.filter(pk=other_area.pk).exists())

    def test_delete_area_keeps_linked_diary(self):
        planner = Planner.objects.create(user=self.user)
        diary = Diary.objects.create(user=self.user, title="Грядка", description="desc")
        area = PlannerArea.objects.create(planner=planner, diary=diary, title="Грядка")

        response = self.client.post(
            reverse("pro_auth:profile-planner-area-delete", kwargs={"pk": area.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlannerArea.objects.filter(pk=area.pk).exists())
        self.assertTrue(Diary.objects.filter(pk=diary.pk).exists())

    def test_create_row_planting_uses_existing_plant_and_links_diary(self):
        category = Category.objects.create(slug="cucumber", value="Огірок")
        plant = Plant.objects.create(user=self.user, category=category, variety="Артист F1")
        diary = Diary.objects.create(user=self.user, title="Теплиця", description="desc")
        planner = Planner.objects.create(user=self.user)
        area = PlannerArea.objects.create(planner=planner, diary=diary, title="Права грядка")

        response = self.client.post(
            reverse("pro_auth:profile-planner-planting-add", kwargs={"area_pk": area.pk}),
            {
                "plant_id": plant.pk,
                "mode": "rows",
                "rows": "3",
                "notes": "Посіяно вздовж стінки",
            },
        )

        self.assertEqual(response.status_code, 201)
        planting = PlannerPlanting.objects.get(area=area, plant=plant)
        self.assertEqual(planting.rows, 3)
        self.assertEqual(planting.layout_summary, "3 ряди")
        self.assertTrue(diary.plants.filter(pk=plant.pk).exists())
        self.assertEqual(response.json()["planting"]["summary"], "3 ряди")

    def test_create_broadcast_planting_does_not_require_quantity(self):
        category = Category.objects.create(slug="arugula", value="Рукола")
        plant = Plant.objects.create(user=self.user, category=category)
        planner = Planner.objects.create(user=self.user)
        area = PlannerArea.objects.create(planner=planner, title="Зелена грядка")

        response = self.client.post(
            reverse("pro_auth:profile-planner-planting-add", kwargs={"area_pk": area.pk}),
            {"plant_id": plant.pk, "mode": "broadcast"},
        )

        self.assertEqual(response.status_code, 201)
        planting = PlannerPlanting.objects.get(area=area, plant=plant)
        self.assertIsNone(planting.quantity)
        self.assertEqual(planting.layout_summary, "суцільний посів")

    def test_create_new_plant_from_planner_syncs_plant_diary_and_history(self):
        species_parent = Category.objects.create(slug="roslinnitstvo", value="Рослинництво")
        category = Category.objects.create(
            slug="cucumber-planner",
            value="Огірок",
            parent=species_parent,
        )
        diary = Diary.objects.create(user=self.user, title="Теплиця", description="desc")
        planner = Planner.objects.create(user=self.user)
        area = PlannerArea.objects.create(planner=planner, diary=diary, title="Ліва грядка")

        response = self.client.post(
            reverse("pro_auth:profile-planner-planting-add", kwargs={"area_pk": area.pk}),
            {
                "plant_source": "new",
                "new_category_id": category.pk,
                "new_variety": "Артист F1",
                "new_title": "лівий ряд",
                "new_plant_date": "2026-06-22",
                "mode": "approximate",
                "quantity": "12",
            },
        )

        self.assertEqual(response.status_code, 201)
        plant = Plant.objects.get(user=self.user, category=category)
        self.assertEqual(plant.variety, "Артист F1")
        self.assertEqual(plant.title, "лівий ряд")
        self.assertTrue(diary.plants.filter(pk=plant.pk).exists())
        self.assertTrue(PlannerPlanting.objects.filter(area=area, plant=plant).exists())
        planted_item = DiaryItem.objects.get(diary=diary, action_type="planted")
        self.assertEqual(list(planted_item.plants.all()), [plant])
        self.assertTrue(response.json()["createdPlant"])

    def test_new_planner_plant_requires_category_variety_or_title(self):
        planner = Planner.objects.create(user=self.user)
        area = PlannerArea.objects.create(planner=planner, title="Грядка")

        response = self.client.post(
            reverse("pro_auth:profile-planner-planting-add", kwargs={"area_pk": area.pk}),
            {"plant_source": "new", "mode": "unknown"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Plant.objects.filter(user=self.user).count(), 0)
        self.assertEqual(PlannerPlanting.objects.filter(area=area).count(), 0)

    def test_delete_planting_keeps_plant_and_diary_membership(self):
        category = Category.objects.create(slug="dill", value="Кріп")
        plant = Plant.objects.create(user=self.user, category=category)
        diary = Diary.objects.create(user=self.user, title="Грядка", description="desc")
        diary.plants.add(plant)
        planner = Planner.objects.create(user=self.user)
        area = PlannerArea.objects.create(planner=planner, diary=diary, title="Грядка")
        planting = PlannerPlanting.objects.create(area=area, plant=plant, mode="unknown")

        response = self.client.post(
            reverse("pro_auth:profile-planner-planting-delete", kwargs={"pk": planting.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlannerPlanting.objects.filter(pk=planting.pk).exists())
        self.assertTrue(Plant.objects.filter(pk=plant.pk).exists())
        self.assertTrue(diary.plants.filter(pk=plant.pk).exists())

    def test_update_planting_clamps_geometry_inside_area(self):
        category = Category.objects.create(slug="basil", value="Базилік")
        plant = Plant.objects.create(user=self.user, category=category)
        planner = Planner.objects.create(user=self.user)
        area = PlannerArea.objects.create(planner=planner, title="Грядка")
        planting = PlannerPlanting.objects.create(area=area, plant=plant)

        response = self.client.post(
            reverse("pro_auth:profile-planner-planting-update", kwargs={"pk": planting.pk}),
            {"x_pct": "90", "y_pct": "95", "width_pct": "30", "height_pct": "40"},
        )

        self.assertEqual(response.status_code, 200)
        planting.refresh_from_db()
        self.assertEqual(planting.x_pct, Decimal("70.00"))
        self.assertEqual(planting.y_pct, Decimal("60.00"))
        self.assertEqual(planting.width_pct, Decimal("30.00"))
        self.assertEqual(planting.height_pct, Decimal("40.00"))

    def test_ready_ai_profile_provides_confirmed_spacing_guidance(self):
        category = Category.objects.create(slug="tomato-planner", value="Томат")
        CategoryAIProfile.objects.create(
            category=category,
            title="Томат: база знань",
            status=CategoryAIProfile.STATUS_READY,
            is_ai_enabled=True,
            content=(
                "## Посадка\n"
                "- Відстань між рослинами: 35–45 см.\n"
                "- Між рядами залишайте 70 см.\n"
                "- Поливати після висадки."
            ),
        )
        plant = Plant.objects.create(user=self.user, category=category)

        guidance = extract_planner_spacing_guidance(plant)

        self.assertEqual(
            guidance["items"],
            ["Відстань між рослинами: 35–45 см.", "Між рядами залишайте 70 см."],
        )
        self.assertEqual(guidance["source"], "Томат: база знань")

    def test_draft_ai_profile_is_not_used_for_spacing_guidance(self):
        category = Category.objects.create(slug="pepper-planner", value="Перець")
        CategoryAIProfile.objects.create(
            category=category,
            status=CategoryAIProfile.STATUS_DRAFT,
            is_ai_enabled=True,
            content="Відстань між рослинами: 40 см.",
        )
        plant = Plant.objects.create(user=self.user, category=category)

        self.assertEqual(extract_planner_spacing_guidance(plant), {"items": [], "source": ""})

    def test_completed_planting_updates_plant_and_diary_history(self):
        category = Category.objects.create(slug="lettuce-planner", value="Салат")
        plant = Plant.objects.create(user=self.user, category=category)
        diary = Diary.objects.create(user=self.user, title="Грядка", description="desc")
        diary.plants.add(plant)
        planner = Planner.objects.create(user=self.user)
        area = PlannerArea.objects.create(planner=planner, diary=diary, title="Грядка")
        planting = PlannerPlanting.objects.create(area=area, plant=plant, status="growing")

        response = self.client.post(
            reverse("pro_auth:profile-planner-planting-update", kwargs={"pk": planting.pk}),
            {"status": "completed"},
        )

        self.assertEqual(response.status_code, 200)
        planting.refresh_from_db()
        plant.refresh_from_db()
        self.assertEqual(planting.status, "completed")
        self.assertEqual(plant.status, "completed")
        self.assertEqual(plant.completed_at, timezone.localdate())
        finished_item = DiaryItem.objects.get(diary=diary, action_type="finished")
        self.assertEqual(list(finished_item.plants.all()), [plant])

        restore_response = self.client.post(
            reverse("pro_auth:profile-planner-planting-update", kwargs={"pk": planting.pk}),
            {"status": "growing"},
        )
        self.assertEqual(restore_response.status_code, 200)
        plant.refresh_from_db()
        self.assertEqual(plant.status, "active")
        self.assertIsNone(plant.completed_at)


class ProfileDiaryDetailFilterTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = Category.objects.create(slug="basil", value="Базилік")
        self.diary = Diary.objects.create(user=self.user, title="Diary", description="desc")
        self.first_plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        self.second_plant = Plant.objects.create(user=self.user, category=self.category, variety="Thai")
        self.completed_plant = Plant.objects.create(
            user=self.user,
            category=self.category,
            variety="Purple",
            status="completed",
        )
        self.diary.plants.set([self.first_plant, self.second_plant, self.completed_plant])

        self.first_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="note",
            description="Листя виглядає добре",
            date="2026-04-24",
        )
        self.first_item.plants.set([self.first_plant])
        self.second_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="watering",
            description="Полив для тайського базиліку",
            date="2026-04-25",
        )
        self.second_item.plants.set([self.second_plant])
        self.third_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="fertilizer",
            description="Травневе підживлення",
            date="2026-05-02",
        )
        self.third_item.plants.set([self.first_plant])

    def test_filter_events_by_plant(self):
        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"plant": self.first_plant.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"], [self.third_item, self.first_item])
        self.assertEqual(response.context["selected_plant_id"], str(self.first_plant.pk))
        self.assertContains(response, f"{self.completed_plant.display_name} (в архіві)")

    def test_search_events_by_description(self):
        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"q": "тайського"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"], [self.second_item])
        self.assertEqual(response.context["event_search_query"], "тайського")

    def test_filter_by_action_type(self):
        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"action": "watering"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"], [self.second_item])
        self.assertEqual(response.context["selected_action_type"], "watering")
        self.assertTrue(response.context["has_active_filters"])

    def test_filter_by_period(self):
        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"period": "2026-04"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_period"], "2026-04")
        self.assertEqual(response.context["diary_items"], [self.second_item, self.first_item])

    def test_filter_by_action_and_plant_and_period(self):
        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"plant": self.first_plant.pk, "action": "fertilizer", "period": "2026-05"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"], [self.third_item])
        self.assertEqual(response.context["selected_plant_id"], str(self.first_plant.pk))
        self.assertEqual(response.context["selected_action_type"], "fertilizer")
        self.assertEqual(response.context["selected_period"], "2026-05")

    def test_invalid_period_does_not_crash(self):
        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"period": "2026-99"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_period"], "2026-99")
        self.assertEqual(response.context["diary_items"], [self.third_item, self.second_item, self.first_item])

    def test_filter_by_action_and_plant(self):
        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"plant": self.second_plant.pk, "action": "watering"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"], [self.second_item])
        self.assertEqual(response.context["selected_plant_id"], str(self.second_plant.pk))
        self.assertEqual(response.context["selected_action_type"], "watering")

    def test_empty_state_for_filtered_results(self):
        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"plant": self.first_plant.pk, "action": "watering", "period": "2026-04"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"], [])
        self.assertContains(response, "Немає подій за вибраними фільтрами")
        self.assertContains(response, "Скинути фільтри")

    def test_action_filter_options_include_all_action_choices(self):
        response = self.client.get(self.diary.get_profile_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["action_filter_options"], [("", "Всі дії"), *DIARY_ITEM_ACTION_CHOICES])

    def test_period_options_include_only_months_with_items(self):
        response = self.client.get(self.diary.get_profile_absolute_url())

        self.assertEqual(
            response.context["period_filter_options"],
            [("", "Всі дати"), ("2026-05", "Травень 2026"), ("2026-04", "Квітень 2026")],
        )

    def test_timeline_renders_date_group_headings(self):
        response = self.client.get(self.diary.get_profile_absolute_url())

        grouped_items = response.context["grouped_diary_items"]
        self.assertEqual(len(grouped_items), 3)
        self.assertEqual(grouped_items[0]["items"], [self.third_item])
        self.assertEqual(grouped_items[1]["items"], [self.second_item])
        self.assertEqual(grouped_items[2]["items"], [self.first_item])

    def test_filter_by_transplanted_action_type(self):
        transplanted_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="transplanted",
            description="Рослину пересаджено до щоденника: Теплиця",
            date="2026-04-26",
            apply_to_all=False,
        )
        transplanted_item.plants.set([self.first_plant])

        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"action": "transplanted"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"], [transplanted_item])
        self.assertEqual(response.context["selected_action_type"], "transplanted")


class PlantMoveFlowTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory(email="move-other@example.com")
        self.client.force_login(self.user)
        self.category = Category.objects.create(slug="tomato", value="Помідор")
        self.source_diary = Diary.objects.create(user=self.user, title="Балкон", description="desc")
        self.target_diary = Diary.objects.create(user=self.user, title="Теплиця", description="desc")
        self.archived_diary = Diary.objects.create(
            user=self.user,
            title="Архів",
            description="desc",
            is_archived=True,
        )
        self.other_user_diary = Diary.objects.create(user=self.other_user, title="Чужий", description="desc")
        self.plant = Plant.objects.create(user=self.user, category=self.category, variety="F1")
        self.source_diary.plants.add(self.plant)
        self.note_item = DiaryItem.objects.create(
            diary=self.source_diary,
            action_type="note",
            description="Перший запис",
            date="2026-04-25",
        )
        self.note_item.plants.set([self.plant])

    def test_can_move_active_plant_to_another_active_diary(self):
        response = self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {"target_diary": self.target_diary.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.source_diary.get_profile_absolute_url(), fetch_redirect_response=False)
        self.assertTrue(self.target_diary.plants.filter(pk=self.plant.pk).exists())
        self.assertFalse(self.source_diary.plants.filter(pk=self.plant.pk).exists())
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.status, "active")

    def test_cannot_move_to_same_diary(self):
        response = self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {"target_diary": self.source_diary.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertIn("target_diary", response.context["form"].errors)
        self.assertTrue(self.source_diary.plants.filter(pk=self.plant.pk).exists())
        self.assertFalse(self.target_diary.plants.filter(pk=self.plant.pk).exists())

    def test_cannot_move_to_archived_diary(self):
        response = self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {"target_diary": self.archived_diary.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertIn("target_diary", response.context["form"].errors)
        self.assertTrue(self.source_diary.plants.filter(pk=self.plant.pk).exists())

    def test_old_diary_items_in_source_diary_remain(self):
        self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {"target_diary": self.target_diary.pk},
        )

        response = self.client.get(self.source_diary.get_profile_absolute_url())
        self.assertContains(response, self.note_item.description)
        transplanted_item = DiaryItem.objects.get(diary=self.source_diary, action_type="transplanted")
        self.assertIn(self.note_item, response.context["diary_items"])
        self.assertIn(transplanted_item, response.context["diary_items"])

    def test_prefixed_move_form_from_detail_modal_moves_plant(self):
        prefix = f"plant-{self.plant.pk}"

        response = self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {
                "_form_prefix": prefix,
                f"{prefix}-target_diary": self.target_diary.pk,
            },
        )

        self.assertRedirects(response, self.source_diary.get_profile_absolute_url(), fetch_redirect_response=False)
        self.assertTrue(self.target_diary.plants.filter(pk=self.plant.pk).exists())
        self.assertFalse(self.source_diary.plants.filter(pk=self.plant.pk).exists())

    def test_move_creates_transplanted_item_in_source_diary(self):
        self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {"target_diary": self.target_diary.pk},
        )

        item = DiaryItem.objects.get(diary=self.source_diary, action_type="transplanted")
        self.assertFalse(item.apply_to_all)
        self.assertEqual(list(item.plants.all()), [self.plant])
        self.assertEqual(item.description, f"Рослину пересаджено до щоденника: {self.target_diary.title}")

    def test_move_creates_transplanted_item_in_target_diary(self):
        self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {"target_diary": self.target_diary.pk},
        )

        item = DiaryItem.objects.get(diary=self.target_diary, action_type="transplanted")
        self.assertFalse(item.apply_to_all)
        self.assertEqual(list(item.plants.all()), [self.plant])
        self.assertEqual(item.description, f"Рослину пересаджено з щоденника: {self.source_diary.title}")

    def test_deleting_source_transplanted_item_undoes_move_everywhere(self):
        self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {"target_diary": self.target_diary.pk},
        )
        source_item = DiaryItem.objects.get(diary=self.source_diary, action_type="transplanted")
        target_item = DiaryItem.objects.get(diary=self.target_diary, action_type="transplanted")

        response = self.client.get(reverse("pro_auth:profile-diary-item-delete", kwargs={"pk": source_item.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.source_diary.get_profile_absolute_url(), fetch_redirect_response=False)
        self.assertTrue(self.source_diary.plants.filter(pk=self.plant.pk).exists())
        self.assertFalse(self.target_diary.plants.filter(pk=self.plant.pk).exists())
        self.assertFalse(DiaryItem.objects.filter(pk=source_item.pk).exists())
        self.assertFalse(DiaryItem.objects.filter(pk=target_item.pk).exists())

    def test_deleting_target_transplanted_item_undoes_move_everywhere(self):
        self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {"target_diary": self.target_diary.pk},
        )
        source_item = DiaryItem.objects.get(diary=self.source_diary, action_type="transplanted")
        target_item = DiaryItem.objects.get(diary=self.target_diary, action_type="transplanted")

        response = self.client.get(reverse("pro_auth:profile-diary-item-delete", kwargs={"pk": target_item.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.source_diary.get_profile_absolute_url(), fetch_redirect_response=False)
        self.assertTrue(self.source_diary.plants.filter(pk=self.plant.pk).exists())
        self.assertFalse(self.target_diary.plants.filter(pk=self.plant.pk).exists())
        self.assertFalse(DiaryItem.objects.filter(pk=source_item.pk).exists())
        self.assertFalse(DiaryItem.objects.filter(pk=target_item.pk).exists())

    def test_source_diary_filter_includes_moved_historical_plant(self):
        self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {"target_diary": self.target_diary.pk},
        )

        response = self.client.get(self.source_diary.get_profile_absolute_url())
        self.assertContains(response, f"{self.plant.display_name} (перенесена)")
        transplanted_item = DiaryItem.objects.get(diary=self.source_diary, action_type="transplanted")
        self.assertIn(self.note_item, response.context["diary_items"])
        self.assertIn(transplanted_item, response.context["diary_items"])

    def test_no_orphan_plant_after_move(self):
        self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            ),
            {"target_diary": self.target_diary.pk},
        )

        self.assertTrue(Plant.objects.filter(pk=self.plant.pk).exists())
        self.assertEqual(list(self.plant.diaries.values_list("pk", flat=True)), [self.target_diary.pk])

    def test_only_owner_can_move_plant_between_own_diaries(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse(
                "pro_auth:profile-diary-plant-move",
                kwargs={"diary_pk": self.source_diary.pk, "plant_pk": self.plant.pk},
            )
        )

        self.assertEqual(response.status_code, 404)


class DiaryFormPlantTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.request = type("Request", (), {"user": self.user})()
        self.species_parent = Category.objects.create(
            slug="plants",
            value="Рослинництво",
            is_diary_species_parent=True,
        )
        self.category = Category.objects.create(
            slug="tomatoes",
            value="Помідор",
            parent=self.species_parent,
        )

    def test_create_diary_with_new_classifier_plant(self):
        form = DiaryForm(
            request=self.request,
            data={
                "title": "Балконний щоденник",
                "description": "desc",
            },
        )
        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            data={
                "plants-TOTAL_FORMS": "1",
                "plants-INITIAL_FORMS": "0",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
                "plants-0-existing_plant": "",
                "plants-0-plant_category": self.category.pk,
                "plants-0-plant_variety": "Cherry",
                "plants-0-plant_title": "",
                "plants-0-plant_description": "Перший сезон",
                "plants-0-plant_date": "2026-04-26",
            },
        )

        self.assertTrue(form.is_valid())
        self.assertTrue(plant_formset.is_valid())
        diary = form.save()
        save_diary_plants(diary, self.user, plant_formset)
        plant = diary.plants.get()

        self.assertEqual(plant.user, self.user)
        self.assertEqual(plant.category, self.category)
        self.assertEqual(plant.variety, "Cherry")
        self.assertEqual(diary.plant_type, "tomatoes")

    def test_plant_formset_requires_selected_or_new_plant(self):
        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            data={
                "plants-TOTAL_FORMS": "0",
                "plants-INITIAL_FORMS": "0",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertFalse(plant_formset.is_valid())
        self.assertIn(
            "Додайте хоча б одну рослину до щоденника.",
            plant_formset.non_form_errors(),
        )

    def test_create_diary_can_attach_existing_plant(self):
        plant = Plant.objects.create(user=self.user, category=self.category, variety="Roma")

        form = DiaryForm(
            request=self.request,
            data={
                "title": "Тепличний щоденник",
                "description": "desc",
            },
        )
        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            data={
                "plants-TOTAL_FORMS": "1",
                "plants-INITIAL_FORMS": "0",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
                "plants-0-existing_plant": plant.pk,
                "plants-0-plant_category": "",
                "plants-0-plant_variety": "",
                "plants-0-plant_title": "",
                "plants-0-plant_description": "",
                "plants-0-plant_date": "",
            },
        )

        self.assertTrue(form.is_valid())
        self.assertTrue(plant_formset.is_valid())
        diary = form.save()
        save_diary_plants(diary, self.user, plant_formset)

        self.assertEqual(list(diary.plants.all()), [plant])
        self.assertEqual(Plant.objects.count(), 1)

    def test_create_diary_cannot_attach_completed_plant(self):
        plant = Plant.objects.create(
            user=self.user,
            category=self.category,
            variety="Roma",
            status="completed",
        )

        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            data={
                "plants-TOTAL_FORMS": "1",
                "plants-INITIAL_FORMS": "0",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
                "plants-0-existing_plant": plant.pk,
                "plants-0-plant_category": "",
                "plants-0-plant_variety": "",
                "plants-0-plant_title": "",
                "plants-0-plant_description": "",
                "plants-0-plant_date": "",
            },
        )

        self.assertFalse(plant_formset.is_valid())
        self.assertIn("existing_plant", plant_formset.forms[0].errors)

    def test_save_diary_plants_keeps_existing_completed_plants_attached(self):
        active_plant = Plant.objects.create(user=self.user, category=self.category, variety="Active")
        completed_plant = Plant.objects.create(
            user=self.user,
            category=self.category,
            variety="Completed",
            status="completed",
        )
        diary = Diary.objects.create(user=self.user, title="Грядка")
        diary.plants.set([active_plant, completed_plant])

        replacement_active = Plant.objects.create(user=self.user, category=self.category, variety="Replacement")
        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            data={
                "plants-TOTAL_FORMS": "1",
                "plants-INITIAL_FORMS": "1",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
                "plants-0-existing_plant": replacement_active.pk,
                "plants-0-plant_category": "",
                "plants-0-plant_variety": "",
                "plants-0-plant_title": "",
                "plants-0-plant_description": "",
                "plants-0-plant_date": "",
                "plants-0-DELETE": "",
            },
            initial=[{"existing_plant": active_plant.pk}],
        )

        self.assertTrue(plant_formset.is_valid())
        save_diary_plants(diary, self.user, plant_formset)

        self.assertCountEqual(diary.plants.values_list("pk", flat=True), [replacement_active.pk, completed_plant.pk])

    def test_update_formset_allows_empty_when_diary_has_completed_plants(self):
        diary = Diary.objects.create(user=self.user, title="Грядка")
        completed_plant = Plant.objects.create(
            user=self.user,
            category=self.category,
            variety="Completed",
            status="completed",
        )
        diary.plants.add(completed_plant)

        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            allow_empty=True,
            data={
                "plants-TOTAL_FORMS": "0",
                "plants-INITIAL_FORMS": "0",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertTrue(plant_formset.is_valid())
        save_diary_plants(diary, self.user, plant_formset)
        self.assertEqual(list(diary.plants.all()), [completed_plant])

    def test_category_picker_only_shows_children_of_roslynnytstvo_parent(self):
        Category.objects.create(
            slug="plants-child-disabled",
            value="Неактивна",
            parent=self.species_parent,
            is_active=False,
        )
        Category.objects.create(slug="other-parent", value="Інший розділ")

        plant_formset = PlantAttachmentFormSet(request=self.request, prefix="plants")
        plant_form = plant_formset.empty_form

        self.assertEqual(list(plant_form.fields["plant_category"].queryset), [self.category])

    def test_remove_unsaved_formset_row_does_not_touch_database(self):
        diary = Diary.objects.create(user=self.user, title="Грядка")
        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            allow_empty=True,
            diary=diary,
            data={
                "plants-TOTAL_FORMS": "1",
                "plants-INITIAL_FORMS": "0",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
                "plants-0-existing_plant": "",
                "plants-0-plant_category": self.category.pk,
                "plants-0-plant_variety": "Cherry",
                "plants-0-plant_title": "",
                "plants-0-plant_description": "temp",
                "plants-0-plant_date": "2026-04-26",
                "plants-0-DELETE": "on",
            },
        )

        self.assertTrue(plant_formset.is_valid())
        save_diary_plants(diary, self.user, plant_formset)

        self.assertEqual(Plant.objects.count(), 0)
        self.assertEqual(diary.plants.count(), 0)

    def test_remove_existing_plant_without_history_hard_deletes_plant(self):
        diary = Diary.objects.create(user=self.user, title="Грядка")
        plant = Plant.objects.create(user=self.user, category=self.category, variety="Roma")
        diary.plants.add(plant)
        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            allow_empty=True,
            diary=diary,
            data={
                "plants-TOTAL_FORMS": "1",
                "plants-INITIAL_FORMS": "1",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
                "plants-0-existing_plant": plant.pk,
                "plants-0-plant_category": "",
                "plants-0-plant_variety": "",
                "plants-0-plant_title": "",
                "plants-0-plant_description": "",
                "plants-0-plant_date": "",
                "plants-0-DELETE": "on",
            },
            initial=[{"existing_plant": plant.pk}],
        )

        self.assertTrue(plant_formset.is_valid())
        save_diary_plants(diary, self.user, plant_formset)

        self.assertFalse(Plant.objects.filter(pk=plant.pk).exists())
        self.assertEqual(diary.plants.count(), 0)

    def test_remove_existing_plant_with_history_marks_completed_and_creates_finished_item(self):
        diary = Diary.objects.create(user=self.user, title="Грядка")
        plant = Plant.objects.create(user=self.user, category=self.category, variety="Roma")
        diary.plants.add(plant)
        note_item = DiaryItem.objects.create(diary=diary, action_type="note", date="2026-04-25")
        note_item.plants.set([plant])
        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            allow_empty=True,
            diary=diary,
            data={
                "plants-TOTAL_FORMS": "1",
                "plants-INITIAL_FORMS": "1",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
                "plants-0-existing_plant": plant.pk,
                "plants-0-plant_category": "",
                "plants-0-plant_variety": "",
                "plants-0-plant_title": "",
                "plants-0-plant_description": "",
                "plants-0-plant_date": "",
                "plants-0-DELETE": "on",
            },
            initial=[{"existing_plant": plant.pk}],
        )

        self.assertTrue(plant_formset.is_valid())
        save_diary_plants(diary, self.user, plant_formset)

        plant.refresh_from_db()
        self.assertEqual(plant.status, "completed")
        self.assertEqual(plant.completed_at, timezone.localdate())
        self.assertTrue(diary.plants.filter(pk=plant.pk).exists())
        finished_item = DiaryItem.objects.get(diary=diary, action_type="finished")
        self.assertFalse(finished_item.apply_to_all)
        self.assertEqual(list(finished_item.plants.all()), [plant])

    def test_remove_existing_plant_with_links_to_other_diaries_is_blocked(self):
        diary = Diary.objects.create(user=self.user, title="Грядка")
        other_diary = Diary.objects.create(user=self.user, title="Інша грядка")
        plant = Plant.objects.create(user=self.user, category=self.category, variety="Roma")
        diary.plants.add(plant)
        other_diary.plants.add(plant)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("pro_auth:profile-diary-update", kwargs={"pk": diary.pk}),
            data={
                "title": "Грядка",
                "description": "",
                "plants-TOTAL_FORMS": "1",
                "plants-INITIAL_FORMS": "1",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
                "plants-0-existing_plant": plant.pk,
                "plants-0-plant_category": "",
                "plants-0-plant_variety": "",
                "plants-0-plant_title": "",
                "plants-0-plant_description": "",
                "plants-0-plant_date": "",
                "plants-0-DELETE": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, PLANT_BLOCKED_TEXT)
        plant.refresh_from_db()
        self.assertEqual(plant.status, "active")
        self.assertTrue(diary.plants.filter(pk=plant.pk).exists())
        self.assertTrue(other_diary.plants.filter(pk=plant.pk).exists())

    def test_remove_existing_plant_with_global_history_is_not_hard_deleted(self):
        diary = Diary.objects.create(user=self.user, title="Грядка")
        other_diary = Diary.objects.create(user=self.user, title="Інша грядка")
        plant = Plant.objects.create(user=self.user, category=self.category, variety="Roma")
        diary.plants.add(plant)
        other_item = DiaryItem.objects.create(diary=other_diary, action_type="note", date="2026-04-25")
        other_item.plants.set([plant])
        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            allow_empty=True,
            diary=diary,
            data={
                "plants-TOTAL_FORMS": "1",
                "plants-INITIAL_FORMS": "1",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
                "plants-0-existing_plant": plant.pk,
                "plants-0-plant_category": "",
                "plants-0-plant_variety": "",
                "plants-0-plant_title": "",
                "plants-0-plant_description": "",
                "plants-0-plant_date": "",
                "plants-0-DELETE": "on",
            },
            initial=[{"existing_plant": plant.pk}],
        )

        self.assertFalse(plant_formset.is_valid())
        self.assertIn(PLANT_BLOCKED_TEXT, plant_formset.non_form_errors())

    def test_remove_existing_plant_without_history_but_attached_to_another_diary_is_not_deleted(self):
        diary = Diary.objects.create(user=self.user, title="Грядка")
        other_diary = Diary.objects.create(user=self.user, title="Інша грядка")
        plant = Plant.objects.create(user=self.user, category=self.category, variety="Roma")
        diary.plants.add(plant)
        other_diary.plants.add(plant)
        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            allow_empty=True,
            diary=diary,
            data={
                "plants-TOTAL_FORMS": "1",
                "plants-INITIAL_FORMS": "1",
                "plants-MIN_NUM_FORMS": "0",
                "plants-MAX_NUM_FORMS": "1000",
                "plants-0-existing_plant": plant.pk,
                "plants-0-plant_category": "",
                "plants-0-plant_variety": "",
                "plants-0-plant_title": "",
                "plants-0-plant_description": "",
                "plants-0-plant_date": "",
                "plants-0-DELETE": "on",
            },
            initial=[{"existing_plant": plant.pk}],
        )

        self.assertFalse(plant_formset.is_valid())
        self.assertIn(PLANT_BLOCKED_TEXT, plant_formset.non_form_errors())

    def test_existing_plant_remove_labels_match_scenario(self):
        diary = Diary.objects.create(user=self.user, title="Грядка")
        deletable_plant = Plant.objects.create(user=self.user, category=self.category, variety="Delete me")
        historical_plant = Plant.objects.create(user=self.user, category=self.category, variety="Finish me")
        blocked_plant = Plant.objects.create(user=self.user, category=self.category, variety="Blocked")
        other_diary = Diary.objects.create(user=self.user, title="Інша грядка")
        diary.plants.set([deletable_plant, historical_plant, blocked_plant])
        other_diary.plants.add(blocked_plant)
        note_item = DiaryItem.objects.create(diary=diary, action_type="note", date="2026-04-25")
        note_item.plants.set([historical_plant])

        plant_formset = PlantAttachmentFormSet(
            request=self.request,
            prefix="plants",
            allow_empty=True,
            diary=diary,
            initial=[
                {"existing_plant": deletable_plant.pk},
                {"existing_plant": historical_plant.pk},
                {"existing_plant": blocked_plant.pk},
            ],
        )

        self.assertEqual(plant_formset.forms[0].remove_label, "Видалити")
        self.assertEqual(plant_formset.forms[1].remove_label, "Завершити цикл")
        self.assertEqual(plant_formset.forms[2].remove_label, "Потрібне перенесення")
        self.assertTrue(plant_formset.forms[2].remove_is_disabled)

    def test_update_page_shows_blocked_remove_message_for_multi_diary_plant(self):
        diary = Diary.objects.create(user=self.user, title="Грядка")
        other_diary = Diary.objects.create(user=self.user, title="Інша грядка")
        blocked_plant = Plant.objects.create(user=self.user, category=self.category, variety="Blocked")
        diary.plants.add(blocked_plant)
        other_diary.plants.add(blocked_plant)

        self.client.force_login(self.user)
        response = self.client.get(reverse("pro_auth:profile-diary-update", kwargs={"pk": diary.pk}))

        self.assertContains(response, "Потрібне перенесення")
        self.assertContains(response, PLANT_BLOCKED_TEXT)


class PlantAutocompleteTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory(email="other-user@example.com")
        self.category = Category.objects.create(slug="basil", value="Базилік")
        self.active_plant = Plant.objects.create(
            user=self.user,
            category=self.category,
            variety="Genovese",
            title="Kitchen basil",
        )
        Plant.objects.create(
            user=self.user,
            category=self.category,
            variety="Purple",
            status="completed",
        )
        Plant.objects.create(
            user=self.other_user,
            category=self.category,
            variety="Other user basil",
        )

    def test_requires_authenticated_user(self):
        response = self.client.get(reverse("diaries:plant-autocomplete"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_returns_only_current_user_active_plants(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("diaries:plant-autocomplete"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(response.json()["results"][0]["id"], str(self.active_plant.pk))
        self.assertEqual(response.json()["results"][0]["text"], str(self.active_plant))
        self.assertIn("selected_text", response.json()["results"][0])


class DiaryItemFormPlantTargetTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = Category.objects.create(slug="basil", value="Базилік")
        self.diary = Diary.objects.create(user=self.user, title="Herbs", description="desc")
        self.active_plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        self.second_active_plant = Plant.objects.create(user=self.user, category=self.category, variety="Thai")
        self.completed_plant = Plant.objects.create(
            user=self.user,
            category=self.category,
            variety="Purple",
            status="completed",
        )
        self.diary.plants.set([self.active_plant, self.second_active_plant, self.completed_plant])

    def test_new_item_defaults_to_all_active_plants(self):
        form = DiaryItemForm(diary=self.diary)

        self.assertTrue(form.initial["apply_to_all"])
        self.assertNotIn("plants", form.initial)
        self.assertEqual(list(form.fields["plants"].queryset), [self.active_plant, self.second_active_plant])

    def test_apply_to_all_false_requires_explicit_plant_selection(self):
        form = DiaryItemForm(
            diary=self.diary,
            data={
                "action_type": "note",
                "description": "Огляд",
                "date": "2026-04-26",
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("plants", form.errors)

    def test_save_with_apply_to_all_applies_to_all_active_plants(self):
        form = DiaryItemForm(
            diary=self.diary,
            data={
                "action_type": "note",
                "apply_to_all": "on",
                "description": "Огляд",
                "date": "2026-04-26",
            },
        )

        self.assertTrue(form.is_valid())
        item = form.save()

        self.assertTrue(item.apply_to_all)
        self.assertEqual(
            list(item.plants.all()),
            [self.active_plant, self.second_active_plant],
        )

    def test_apply_to_all_true_excludes_completed_plants(self):
        form = DiaryItemForm(
            diary=self.diary,
            data={
                "action_type": "note",
                "apply_to_all": "on",
                "description": "Огляд",
                "date": "2026-04-26",
            },
        )

        self.assertTrue(form.is_valid())
        item = form.save()

        self.assertEqual(
            list(item.plants.all()),
            [self.active_plant, self.second_active_plant],
        )
        self.assertNotIn(self.completed_plant, item.plants.all())

    def test_save_with_selected_plants_applies_to_concrete_plants(self):
        form = DiaryItemForm(
            diary=self.diary,
            data={
                "action_type": "watering",
                "plants": [self.second_active_plant.pk],
                "description": "Полив",
                "date": "2026-04-26",
            },
        )

        self.assertTrue(form.is_valid())
        item = form.save()

        self.assertFalse(item.apply_to_all)
        self.assertEqual(list(item.plants.all()), [self.second_active_plant])

    def test_harvest_action_requires_amount_and_unit(self):
        form = DiaryItemForm(
            diary=self.diary,
            data={
                "action_type": "harvest",
                "apply_to_all": "on",
                "description": "Збір зелені",
                "date": "2026-04-26",
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("harvest_amount", form.errors)
        self.assertIn("harvest_unit", form.errors)

    def test_harvest_action_saves_amount_and_unit(self):
        form = DiaryItemForm(
            diary=self.diary,
            data={
                "action_type": "harvest",
                "apply_to_all": "on",
                "description": "Збір зелені",
                "harvest_amount": "1.20",
                "harvest_unit": "kg",
                "date": "2026-04-26",
            },
        )

        self.assertTrue(form.is_valid())
        item = form.save()

        self.assertEqual(item.harvest_summary, "1.2 кг")

    def test_non_harvest_action_clears_harvest_fields(self):
        item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="harvest",
            apply_to_all=True,
            harvest_amount="1.20",
            harvest_unit="kg",
            date="2026-04-25",
        )
        item.plants.set([self.active_plant, self.second_active_plant])

        form = DiaryItemForm(
            diary=self.diary,
            instance=item,
            data={
                "action_type": "watering",
                "apply_to_all": "on",
                "description": "Полив",
                "harvest_amount": "1.20",
                "harvest_unit": "kg",
                "date": "2026-04-26",
            },
        )

        self.assertTrue(form.is_valid())
        updated_item = form.save()

        self.assertIsNone(updated_item.harvest_amount)
        self.assertEqual(updated_item.harvest_unit, "")

    def test_edit_item_from_apply_to_all_true_to_false(self):
        item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="note",
            apply_to_all=True,
            date="2026-04-25",
        )
        item.plants.set([self.active_plant, self.second_active_plant])

        form = DiaryItemForm(
            diary=self.diary,
            instance=item,
            data={
                "action_type": "watering",
                "plants": [self.second_active_plant.pk],
                "description": "Полив",
                "date": "2026-04-26",
            },
        )

        self.assertTrue(form.is_valid())
        updated_item = form.save()

        self.assertFalse(updated_item.apply_to_all)
        self.assertEqual(list(updated_item.plants.all()), [self.second_active_plant])
        self.assertNotIn(self.active_plant, updated_item.plants.all())

    def test_edit_item_from_apply_to_all_false_to_true(self):
        item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="note",
            apply_to_all=False,
            date="2026-04-25",
        )
        item.plants.set([self.second_active_plant])

        form = DiaryItemForm(
            diary=self.diary,
            instance=item,
            data={
                "action_type": "watering",
                "apply_to_all": "on",
                "description": "Оновлення",
                "date": "2026-04-26",
            },
        )

        self.assertTrue(form.is_valid())
        updated_item = form.save()

        self.assertTrue(updated_item.apply_to_all)
        self.assertCountEqual(
            updated_item.plants.values_list("pk", flat=True),
            [self.active_plant.pk, self.second_active_plant.pk],
        )

    def test_finished_action_marks_selected_plants_completed(self):
        form = DiaryItemForm(
            diary=self.diary,
            data={
                "action_type": "finished",
                "plants": [self.second_active_plant.pk],
                "description": "Рослину прибрали",
                "date": "2026-04-26",
            },
        )

        self.assertTrue(form.is_valid())
        form.save()

        self.active_plant.refresh_from_db()
        self.second_active_plant.refresh_from_db()

        self.assertEqual(self.active_plant.status, "active")
        self.assertIsNone(self.active_plant.completed_at)
        self.assertEqual(self.second_active_plant.status, "completed")
        self.assertEqual(self.second_active_plant.completed_at.isoformat(), "2026-04-26")

    def test_finished_action_without_selection_marks_all_active_plants_completed(self):
        form = DiaryItemForm(
            diary=self.diary,
            data={
                "action_type": "finished",
                "apply_to_all": "on",
                "description": "Сезон завершено",
                "date": "2026-04-26",
            },
        )

        self.assertTrue(form.is_valid())
        form.save()

        self.active_plant.refresh_from_db()
        self.second_active_plant.refresh_from_db()
        self.completed_plant.refresh_from_db()

        self.assertEqual(self.active_plant.status, "completed")
        self.assertEqual(self.second_active_plant.status, "completed")
        self.assertEqual(self.completed_plant.completed_at, None)

    def test_cannot_create_action_when_diary_has_no_active_plants(self):
        completed_only_diary = Diary.objects.create(user=self.user, title="Completed only", description="desc")
        completed_plant = Plant.objects.create(
            user=self.user,
            category=self.category,
            variety="Old plant",
            status="completed",
        )
        completed_only_diary.plants.add(completed_plant)

        form = DiaryItemForm(
            diary=completed_only_diary,
            data={
                "action_type": "note",
                "apply_to_all": "on",
                "description": "Огляд",
                "date": "2026-04-26",
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "У цьому щоденнику немає активних рослин. Додайте нову рослину, щоб створити дію.",
            form.non_field_errors(),
        )
        self.assertEqual(DiaryItem.objects.filter(diary=completed_only_diary).count(), 0)

    def test_searches_active_plants(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("diaries:plant-autocomplete") + "?q=geno")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(response.json()["results"][0]["id"], str(self.active_plant.pk))


class DiaryItemActionAvailabilityTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = Category.objects.create(slug="basil", value="Базилік")
        self.diary = Diary.objects.create(user=self.user, title="Herbs", description="desc")
        self.first_plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        self.second_plant = Plant.objects.create(user=self.user, category=self.category, variety="Thai")
        self.diary.plants.set([self.first_plant, self.second_plant])

    def test_create_form_excludes_planted_and_transplanted_actions(self):
        form = DiaryItemForm(diary=self.diary)
        action_values = [value for value, _label in form.fields["action_type"].choices]

        self.assertNotIn("planted", action_values)
        self.assertNotIn("transplanted", action_values)

    def test_edit_form_keeps_existing_transplanted_action_available(self):
        item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="transplanted",
            apply_to_all=False,
            date="2026-05-05",
            description="Рослину пересаджено до щоденника: Теплиця",
        )
        item.plants.set([self.first_plant])

        form = DiaryItemForm(diary=self.diary, instance=item)
        action_values = [value for value, _label in form.fields["action_type"].choices]

        self.assertIn("transplanted", action_values)

    def test_create_view_rejects_planted_action_from_manual_post(self):
        response = self.client.post(
            reverse("pro_auth:profile-diary-item-add", kwargs={"diary_id": self.diary.pk}),
            {
                "action_type": "planted",
                "apply_to_all": "on",
                "description": "Посадка",
                "date": "2026-05-05",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertIn("action_type", response.context["form"].errors)
        self.assertFalse(DiaryItem.objects.filter(diary=self.diary, action_type="planted").exists())

    def test_create_view_rejects_transplanted_action_from_manual_post(self):
        response = self.client.post(
            reverse("pro_auth:profile-diary-item-add", kwargs={"diary_id": self.diary.pk}),
            {
                "action_type": "transplanted",
                "plants": [self.first_plant.pk],
                "description": "Пересадка",
                "date": "2026-05-05",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertIn("action_type", response.context["form"].errors)
        self.assertFalse(DiaryItem.objects.filter(diary=self.diary, action_type="transplanted").exists())


class PlantingFlowTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = Category.objects.create(slug="pepper", value="Перець")
        self.diary = Diary.objects.create(user=self.user, title="Теплиця", description="desc")
        self.archived_diary = Diary.objects.create(
            user=self.user,
            title="Архів",
            description="desc",
            is_archived=True,
        )

    def test_can_plant_new_plant_and_create_planted_timeline_item(self):
        response = self.client.post(
            reverse("pro_auth:profile-diary-plant-add", kwargs={"diary_id": self.diary.pk}),
            {
                "plant_variety": "California Wonder",
                "plant_title": "Перець біля входу",
                "plant_description": "Висадила нову розсаду",
                "plant_date": "2026-05-06",
            },
        )

        self.assertRedirects(response, self.diary.get_profile_absolute_url(), fetch_redirect_response=False)
        plant = Plant.objects.get(user=self.user, variety="California Wonder")
        planted_item = DiaryItem.objects.get(diary=self.diary, action_type="planted")

        self.assertTrue(self.diary.plants.filter(pk=plant.pk).exists())
        self.assertEqual(plant.title, "Перець біля входу")
        self.assertEqual(plant.description, "Висадила нову розсаду")
        self.assertEqual(plant.plant_date.isoformat(), "2026-05-06")
        self.assertFalse(planted_item.apply_to_all)
        self.assertEqual(planted_item.date.isoformat(), "2026-05-06")
        self.assertEqual(planted_item.description, "Висадила нову розсаду")
        self.assertEqual(list(planted_item.plants.all()), [plant])

    def test_planting_flow_is_unavailable_for_archived_diary(self):
        response = self.client.get(
            reverse("pro_auth:profile-diary-plant-add", kwargs={"diary_id": self.archived_diary.pk})
        )

        self.assertEqual(response.status_code, 404)


class PlantLifecycleActionTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = Category.objects.create(slug="cucumber", value="Огірок")
        self.diary = Diary.objects.create(user=self.user, title="Теплиця", description="desc")
        self.growing_plant = Plant.objects.create(user=self.user, category=self.category, variety="a1")
        self.archived_plant = Plant.objects.create(
            user=self.user,
            category=self.category,
            variety="a2",
            status="completed",
            completed_at="2026-05-01",
        )
        self.diary.plants.add(self.growing_plant, self.archived_plant)

    def test_detail_uses_growing_and_archive_tab_labels(self):
        response = self.client.get(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))

        self.assertContains(response, "Ростуть")
        self.assertContains(response, "Архів")
        self.assertContains(response, "profile-sidebar-nav")
        self.assertNotContains(response, "profile-layout-row profile-layout-row--full")

    def test_detail_renders_plant_move_and_archive_modals(self):
        response = self.client.get(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))

        self.assertContains(response, f'id="plantMoveModal{self.growing_plant.pk}"')
        self.assertContains(response, f'id="plantArchiveModal{self.growing_plant.pk}"')
        self.assertContains(response, f'data-plant-move-open="plantMoveModal{self.growing_plant.pk}"')
        self.assertContains(response, f'data-plant-archive-open="plantArchiveModal{self.growing_plant.pk}"')
        self.assertContains(response, 'name="_form_prefix"')
        self.assertContains(response, f'value="plant-{self.growing_plant.pk}"')

    def test_detail_renders_quick_watering_panel(self):
        response = self.client.get(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))

        self.assertContains(response, "Швидкі дії")
        self.assertContains(response, f'data-quick-water-open="quickWateringModal{self.diary.pk}"')
        self.assertContains(response, f'id="quickWateringModal{self.diary.pk}"')
        self.assertContains(response, f'name="next" value="{self.diary.get_profile_absolute_url()}"')

    def test_detail_without_active_plants_renders_status_banner(self):
        self.growing_plant.status = "completed"
        self.growing_plant.completed_at = timezone.localdate()
        self.growing_plant.save(update_fields=["status", "completed_at"])

        response = self.client.get(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))

        self.assertContains(response, "У цьому щоденнику зараз немає активних рослин")
        self.assertContains(response, "profile-diary-status-banner")
        self.assertNotContains(response, "Швидкі дії")

    def test_archive_plant_marks_it_completed_and_creates_finished_item(self):
        response = self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-archive",
                kwargs={"diary_pk": self.diary.pk, "plant_pk": self.growing_plant.pk},
            )
        )

        self.assertRedirects(response, self.diary.get_profile_absolute_url(), fetch_redirect_response=False)
        self.growing_plant.refresh_from_db()
        self.assertEqual(self.growing_plant.status, "completed")
        self.assertEqual(self.growing_plant.completed_at, timezone.localdate())
        finished_item = DiaryItem.objects.get(diary=self.diary, action_type="finished", plants=self.growing_plant)
        self.assertFalse(finished_item.apply_to_all)

    def test_restore_plant_from_archive_makes_it_active_and_removes_latest_finished_item(self):
        finished_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="finished",
            apply_to_all=False,
            date="2026-05-01",
        )
        finished_item.plants.set([self.archived_plant])

        response = self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-restore",
                kwargs={"diary_pk": self.diary.pk, "plant_pk": self.archived_plant.pk},
            )
        )

        self.assertRedirects(response, self.diary.get_profile_absolute_url(), fetch_redirect_response=False)
        self.archived_plant.refresh_from_db()
        self.assertEqual(self.archived_plant.status, "active")
        self.assertIsNone(self.archived_plant.completed_at)
        self.assertFalse(DiaryItem.objects.filter(pk=finished_item.pk).exists())

    def test_delete_plant_removes_plant_and_single_target_history(self):
        note_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="note",
            description="Окрема історія рослини",
            date="2026-05-02",
        )
        note_item.plants.set([self.growing_plant])

        response = self.client.post(
            reverse(
                "pro_auth:profile-diary-plant-delete",
                kwargs={"diary_pk": self.diary.pk, "plant_pk": self.growing_plant.pk},
            )
        )

        self.assertRedirects(response, self.diary.get_profile_absolute_url(), fetch_redirect_response=False)
        self.assertFalse(Plant.objects.filter(pk=self.growing_plant.pk).exists())
        self.assertFalse(DiaryItem.objects.filter(pk=note_item.pk).exists())


class DiaryItemTimelineRenderingTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = Category.objects.create(slug="basil", value="Базилік")
        self.diary = Diary.objects.create(user=self.user, title="Herbs", description="desc")
        self.first_plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        self.second_plant = Plant.objects.create(user=self.user, category=self.category, variety="Thai")
        self.third_plant = Plant.objects.create(user=self.user, category=self.category, variety="Purple")
        self.diary.plants.set([self.first_plant, self.second_plant, self.third_plant])

    def test_timeline_renders_apply_to_all_label(self):
        item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="note",
            apply_to_all=True,
            date="2026-04-26",
        )
        item.plants.set([self.first_plant, self.second_plant, self.third_plant])

        response = self.client.get(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Для всіх активних рослин")

    def test_timeline_renders_single_plant(self):
        item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="note",
            apply_to_all=False,
            date="2026-04-26",
        )
        item.plants.set([self.second_plant])

        response = self.client.get(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.second_plant.display_name)

    def test_timeline_renders_multiple_plants(self):
        item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="note",
            apply_to_all=False,
            date="2026-04-26",
        )
        item.plants.set([self.first_plant, self.second_plant, self.third_plant])

        response = self.client.get(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.first_plant.display_name)
        self.assertContains(response, self.second_plant.display_name)
        self.assertContains(response, self.third_plant.display_name)

    def test_detail_renders_add_action_modal_form(self):
        response = self.client.get(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-diary-item-modal-open")
        self.assertContains(response, 'id="diaryItemAddModal"')
        self.assertContains(response, reverse("pro_auth:profile-diary-item-add", kwargs={"diary_id": self.diary.pk}))
        self.assertContains(response, "Оберіть швидку дію")


class DiaryItemDeleteLifecycleTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = Category.objects.create(slug="basil", value="Базилік")
        self.diary = Diary.objects.create(user=self.user, title="Herbs", description="desc")
        self.plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        self.diary.plants.add(self.plant)

    def test_finished_action_delete_returns_plant_to_active(self):
        finished_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="finished",
            apply_to_all=False,
            date="2026-04-26",
        )
        finished_item.plants.set([self.plant])
        self.plant.status = "completed"
        self.plant.completed_at = finished_item.date
        self.plant.save(update_fields=["status", "completed_at"])

        response = self.client.get(reverse("pro_auth:profile-diary-item-delete", kwargs={"pk": finished_item.pk}))

        self.assertEqual(response.status_code, 302)
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.status, "active")
        self.assertIsNone(self.plant.completed_at)

    def test_non_finished_action_delete_does_not_change_plant_status(self):
        note_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="note",
            apply_to_all=False,
            date="2026-04-26",
        )
        note_item.plants.set([self.plant])
        self.plant.status = "completed"
        self.plant.completed_at = note_item.date
        self.plant.save(update_fields=["status", "completed_at"])

        response = self.client.get(reverse("pro_auth:profile-diary-item-delete", kwargs={"pk": note_item.pk}))

        self.assertEqual(response.status_code, 302)
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.status, "completed")
        self.assertEqual(self.plant.completed_at.isoformat(), "2026-04-26")

    def test_deleting_latest_finished_action_restores_previous_finished_state(self):
        older_finished_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="finished",
            apply_to_all=False,
            date="2026-04-20",
        )
        older_finished_item.plants.set([self.plant])
        latest_finished_item = DiaryItem.objects.create(
            diary=self.diary,
            action_type="finished",
            apply_to_all=False,
            date="2026-04-26",
        )
        latest_finished_item.plants.set([self.plant])
        self.plant.status = "completed"
        self.plant.completed_at = latest_finished_item.date
        self.plant.save(update_fields=["status", "completed_at"])

        response = self.client.get(
            reverse("pro_auth:profile-diary-item-delete", kwargs={"pk": latest_finished_item.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.status, "completed")
        self.assertEqual(self.plant.completed_at.isoformat(), "2026-04-20")


CUCUMBER_TEST_KNOWLEDGE = """
1. Базова ідентифікація

Культура: огірок
Наукова назва: Cucumis sativus

5. Полив

Огірок має високі потреби у воді.
Ознаки нестачі води: в'янення, повільний ріст, гіркі плоди.

17. Хвороби

Борошниста роса: білий порошкоподібний наліт.

24. Severity / Priority Signals

Medium severity: поява борошнистої роси.
""".strip()

CUCUMBER_TEST_RULES = """
Rule ID:

cucumber_powdery_mildew_suspected_01

Trigger:

leaves_have_white_powder = true

Additional signals:

Known signals:

user_note_contains: "білий наліт"
user_note_contains: "наче мука"

Assumption:

можлива борошниста роса

Outcome:

powdery_mildew_risk ↑

Confidence:
High

Recommendation:

Покращити циркуляцію повітря.
Прибрати сильно уражене листя.

Do not recommend:

не ставити остаточний діагноз без фото.

Source / basis:

University of Minnesota cucumber guide
""".strip()

ARUGULA_LEGACY_TEST_RULES = """
21. AI Rules для руколи
arugula_heat_bolting_risk_01

Якщо:

температура >29°C;
рослина на повному сонці;
з’являється квітконос.

Тоді: ризик bolting ↑
Confidence: High
Пояснення: рукола швидко стрілкується в жарку погоду.
Рекомендація: притінення, регулярний полив або новий посів у прохолодніший період.

arugula_underwatering_stress_01

Якщо:

ґрунт сухий;
листя в’яне;
давно не було поливу.

Тоді: ризик нестачі води ↑
Confidence: High
Рекомендація: помірний полив, не допускати повного пересихання.

22. Severity / Priority Signals
""".strip()

CUCUMBER_MATCHER_RULES = [
    {"id": "cucumber_pollination_failure_01", "noteSignals": ["багато квітів", "немає огірків", "зав'язі не ростуть"]},
    {
        "id": "cucumber_parthenocarpic_pollination_confusion_01",
        "noteSignals": ["потрібні бджоли", "немає запилення", "теплиця"],
    },
    {"id": "cucumber_irregular_watering_01", "noteSignals": ["гіркі", "деформовані", "то сухо то мокро"]},
    {
        "id": "cucumber_overripe_fruit_reducing_yield_01",
        "noteSignals": ["переросли", "великі огірки", "нові не ростуть"],
    },
    {"id": "cucumber_powdery_mildew_suspected_01", "noteSignals": ["білий наліт", "наче мука", "білі плями"]},
    {"id": "cucumber_bacterial_wilt_risk_01", "noteSignals": ["раптово зів'яв", "огірковий жук", "листя висить"]},
    {"id": "cucumber_greenhouse_airflow_01", "noteSignals": ["теплиця", "конденсат", "волога", "погана вентиляція"]},
    {"id": "cucumber_cold_soil_stress_01", "noteSignals": ["не росте", "після висадки", "холодно"]},
    {"id": "cucumber_crop_rotation_needed_01", "noteSignals": ["саджу щороку", "те саме місце"]},
    {"id": "cucumber_unknown_diagnosis_caution_01", "noteSignals": ["жовтіє", "в'яне", "плями", "не росте"]},
]

CUCUMBER_RECOMMENDATION_SCENARIOS = [
    ("Багато квітів, але немає огірків", "cucumber_pollination_failure_01"),
    ("Зав'язі не ростуть уже тиждень", "cucumber_pollination_failure_01"),
    ("У теплиці немає запилення, потрібні бджоли", "cucumber_parthenocarpic_pollination_confusion_01"),
    ("Плоди стали гіркі", "cucumber_irregular_watering_01"),
    ("Полив то сухо то мокро, плоди деформовані", "cucumber_irregular_watering_01"),
    ("Кілька огірків переросли", "cucumber_overripe_fruit_reducing_yield_01"),
    ("Залишилися великі огірки, а нові не ростуть", "cucumber_overripe_fruit_reducing_yield_01"),
    ("На листі білий наліт", "cucumber_powdery_mildew_suspected_01"),
    ("Білі плями, наче мука", "cucumber_powdery_mildew_suspected_01"),
    ("Кущ раптово зів'яв", "cucumber_bacterial_wilt_risk_01"),
    ("Помітила огірковий жук, листя висить", "cucumber_bacterial_wilt_risk_01"),
    ("У теплиці конденсат і погана вентиляція", "cucumber_greenhouse_airflow_01"),
    ("У теплиці постійна волога", "cucumber_greenhouse_airflow_01"),
    ("Після висадки холодно і огірок не росте", "cucumber_cold_soil_stress_01"),
    ("Саджу щороку на те саме місце", "cucumber_crop_rotation_needed_01"),
    ("Листя жовтіє, з'явилися плями", "cucumber_unknown_diagnosis_caution_01"),
    ("Огірок росте нормально, нових симптомів немає", None),
    ("Рослина в'яне і не росте", "cucumber_unknown_diagnosis_caution_01"),
]


class PlantRecommendationServiceTests(TestCase):
    def test_cucumber_recommendation_scenarios_choose_expected_primary_rule(self):
        self.assertEqual(len(CUCUMBER_RECOMMENDATION_SCENARIOS), 18)

        for note, expected_rule_id in CUCUMBER_RECOMMENDATION_SCENARIOS:
            with self.subTest(note=note):
                matched_rules = selectRelevantRecommendationRules(
                    CUCUMBER_MATCHER_RULES,
                    action_type="note",
                    note=note,
                )
                actual_rule_id = matched_rules[0]["id"] if matched_rules else None
                self.assertEqual(actual_rule_id, expected_rule_id)

    def test_parser_preserves_existing_admin_rule_meaning(self):
        rules = parsePlantRecommendationRules(CUCUMBER_TEST_RULES)

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "cucumber_powdery_mildew_suspected_01")
        self.assertEqual(rules[0]["assumption"], "можлива борошниста роса")
        self.assertIn("Покращити циркуляцію повітря.", rules[0]["recommendation"])
        self.assertEqual(rules[0]["doNotRecommend"], "не ставити остаточний діагноз без фото.")
        self.assertEqual(rules[0]["noteSignals"], ["білий наліт", "наче мука"])

    def test_rule_matcher_finds_cucumber_rule_from_user_note(self):
        rules = parsePlantRecommendationRules(CUCUMBER_TEST_RULES)

        matched_rules = selectRelevantRecommendationRules(
            rules,
            action_type="note",
            note="На листі з'явився білий наліт, наче мука",
        )

        self.assertEqual(matched_rules[0]["id"], "cucumber_powdery_mildew_suspected_01")
        self.assertEqual(matched_rules[0]["matchedSignals"], ["білий наліт", "наче мука"])

    def test_rule_matcher_does_not_fire_without_matching_trigger_signal(self):
        rules = parsePlantRecommendationRules(CUCUMBER_TEST_RULES)

        matched_rules = selectRelevantRecommendationRules(
            rules,
            action_type="disease",
            note="Потрібно оглянути рослину",
        )

        self.assertEqual(matched_rules, [])

    def test_parser_supports_existing_ukrainian_rule_format(self):
        rules = parsePlantRecommendationRules(ARUGULA_LEGACY_TEST_RULES)

        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0]["id"], "arugula_heat_bolting_risk_01")
        self.assertEqual(
            rules[0]["noteSignals"],
            [
                "температура >29°C",
                "рослина на повному сонці",
                "з’являється квітконос",
            ],
        )
        self.assertEqual(rules[0]["outcome"], "ризик bolting ↑")
        self.assertEqual(rules[0]["confidence"], "High")
        self.assertIn("притінення", rules[0]["recommendation"])

    def test_rule_matcher_finds_legacy_arugula_rule(self):
        rules = parsePlantRecommendationRules(ARUGULA_LEGACY_TEST_RULES)

        matched_rules = selectRelevantRecommendationRules(
            rules,
            action_type="note",
            note="Сьогодні листя в’яне і ґрунт сухий",
        )

        self.assertEqual(matched_rules[0]["id"], "arugula_underwatering_stress_01")
        self.assertEqual(matched_rules[0]["matchedSignals"], ["ґрунт сухий", "листя в’яне"])

    def test_rule_matcher_uses_action_interval_condition(self):
        rules = parsePlantRecommendationRules("""
Rule ID:
cucumber_irregular_watering_01

Trigger:
action_type = watering
days_since_previous_watering <= 1

Confidence:
High

Severity:
medium

Recommendation:
Перевірити вологість ґрунту перед наступним поливом.
""".strip())

        matched_rules = selectRelevantRecommendationRules(
            rules,
            action_type="watering",
            note="",
            last_actions=[
                {"action_type": "watering", "date": "2026-06-18"},
                {"action_type": "watering", "date": "2026-06-17"},
            ],
        )

        self.assertEqual(matched_rules[0]["id"], "cucumber_irregular_watering_01")
        self.assertEqual(
            matched_rules[0]["matchedConditions"],
            ["action_type=watering", "days_since_previous_watering=1"],
        )

        unmatched_rules = selectRelevantRecommendationRules(
            rules,
            action_type="watering",
            note="",
            last_actions=[
                {"action_type": "watering", "date": "2026-06-18"},
                {"action_type": "watering", "date": "2026-06-15"},
            ],
        )
        self.assertEqual(unmatched_rules, [])

    def test_knowledge_context_uses_only_ready_enabled_profile(self):
        user = UserFactory()
        cucumber = Category.objects.create(slug="cucumber", value="Огірок")
        arugula = Category.objects.create(slug="arugula", value="Рукола")
        cucumber_plant = Plant.objects.create(user=user, category=cucumber, variety="Тепличний")
        arugula_plant = Plant.objects.create(user=user, category=arugula, variety="Салатна")
        CategoryAIProfile.objects.create(
            category=cucumber,
            status=CategoryAIProfile.STATUS_READY,
            is_ai_enabled=True,
            content=CUCUMBER_TEST_KNOWLEDGE,
            recommendation_rules=CUCUMBER_TEST_RULES,
        )
        CategoryAIProfile.objects.create(
            category=arugula,
            status=CategoryAIProfile.STATUS_DRAFT,
            is_ai_enabled=True,
            content="1. Базова ідентифікація\nКультура: рукола",
        )

        contexts = buildPlantKnowledgeContext(
            plants=[cucumber_plant, arugula_plant],
            action_type="note",
            note="На листі білий наліт",
        )

        self.assertEqual([context["category"] for context in contexts], ["Огірок"])
        self.assertIn("Культура: огірок", contexts[0]["knowledge"])
        self.assertEqual(
            contexts[0]["matchedRules"][0]["id"],
            "cucumber_powdery_mildew_suspected_01",
        )

    def test_fallback_uses_matched_cucumber_rule(self):
        user = UserFactory()
        cucumber = Category.objects.create(slug="cucumber", value="Огірок")
        plant = Plant.objects.create(user=user, category=cucumber, variety="Тепличний")
        CategoryAIProfile.objects.create(
            category=cucumber,
            status=CategoryAIProfile.STATUS_READY,
            is_ai_enabled=True,
            content=CUCUMBER_TEST_KNOWLEDGE,
            recommendation_rules=CUCUMBER_TEST_RULES,
        )

        recommendation = PlantRecommendationService().generate(
            plant_name=plant.display_name,
            plant_date=plant.plant_date,
            action_type="note",
            note="На листі білий наліт",
            last_actions=[{"action_type": "note", "date": "2026-06-18", "has_photo": False}],
            has_photo=False,
            plants=[plant],
            use_ai=False,
        )

        self.assertEqual(
            recommendation["matchedRuleIds"],
            ["cucumber_powdery_mildew_suspected_01"],
        )
        self.assertEqual(recommendation["confidence"], "high")
        self.assertEqual(recommendation["severity"], "medium")
        self.assertEqual(recommendation["nextStep"], "Покращити циркуляцію повітря.")
        self.assertTrue(recommendation["needsMoreData"])
        self.assertEqual(
            recommendation["missingData"],
            [
                "фото листя зверху і знизу",
                "середовище вирощування: теплиця чи відкритий ґрунт",
            ],
        )
        self.assertIn("фото листя", recommendation["clarifyingQuestion"])
        self.assertEqual(recommendation["sourceBasis"], ["University of Minnesota cucumber guide"])

    def test_fallback_does_not_request_known_diagnostic_context(self):
        user = UserFactory()
        cucumber = Category.objects.create(slug="cucumber", value="Огірок")
        plant = Plant.objects.create(user=user, category=cucumber, variety="Тепличний")
        CategoryAIProfile.objects.create(
            category=cucumber,
            status=CategoryAIProfile.STATUS_READY,
            is_ai_enabled=True,
            content=CUCUMBER_TEST_KNOWLEDGE,
            recommendation_rules=CUCUMBER_TEST_RULES,
        )

        recommendation = PlantRecommendationService().generate(
            plant_name=plant.display_name,
            plant_date=plant.plant_date,
            action_type="note",
            note="У теплиці на листі білий наліт",
            last_actions=[{"action_type": "note", "date": "2026-06-19"}],
            has_photo=True,
            plants=[plant],
            use_ai=False,
        )

        self.assertFalse(recommendation["needsMoreData"])
        self.assertEqual(recommendation["missingData"], [])
        self.assertEqual(recommendation["clarifyingQuestion"], "")

    def test_prepare_payload_collects_expected_context(self):
        user = UserFactory()
        category = Category.objects.create(slug="tomato", value="Помідор")
        plant = Plant.objects.create(
            user=user,
            category=category,
            title="Cherry",
            variety="Солодкий 100",
            plant_date="2026-04-01",
        )
        plant.refresh_from_db()
        payload = preparePlantRecommendationPayload(
            plant_name="Cherry",
            plant_date=None,
            action_type="disease",
            note="<p>Плями на листі</p>",
            last_actions=[
                {
                    "action_type": "watering",
                    "date": "2026-04-15",
                    "note": "Полив теплою водою",
                    "has_photo": False,
                },
                {"action_type": "photo", "date": "2026-04-16", "has_photo": True},
            ],
            has_photo=True,
            plants=[plant],
        )

        self.assertEqual(payload["plantName"], "Cherry")
        self.assertEqual(payload["latestAction"]["actionType"], "disease")
        self.assertEqual(payload["note"], "Плями на листі")
        self.assertEqual(len(payload["lastActions"]), 2)
        self.assertEqual(payload["plants"][0]["category"], "Помідор")
        self.assertEqual(payload["plants"][0]["variety"], "Солодкий 100")
        self.assertEqual(payload["plants"][0]["plantDate"], "2026-04-01")
        self.assertIsNone(payload["plants"][0]["growingEnvironment"])
        self.assertEqual(payload["recentActivity"]["watering"]["note"], "Полив теплою водою")
        self.assertIsNone(payload["recentActivity"]["fertilizer"])
        self.assertTrue(payload["hasPhoto"])
        self.assertTrue(payload["preparedAt"])

    def test_prompt_builders_include_payload_context(self):
        payload = preparePlantRecommendationPayload(
            plant_name="Cherry",
            plant_date=None,
            action_type="pest",
            note="Помітили шкідника",
            last_actions=[],
            has_photo=False,
        )

        system_prompt = buildPlantRecommendationSystemPrompt()
        user_prompt = buildPlantRecommendationUserPrompt(payload)

        self.assertIn("Поверни JSON об'єкт", system_prompt)
        self.assertIn('"plantName": "Cherry"', user_prompt)
        self.assertIn('"actionType": "pest"', user_prompt)

    def test_generate_returns_high_severity_for_disease(self):
        recommendation = PlantRecommendationService().generate(
            plant_name="Cherry",
            plant_date=None,
            action_type="disease",
            note="<p>Плями на листі</p>",
            last_actions=[
                {"action_type": "watering", "date": "2026-04-15", "has_photo": False},
                {"action_type": "photo", "date": "2026-04-16", "has_photo": True},
            ],
            has_photo=True,
            use_ai=False,
        )

        self.assertEqual(recommendation["severity"], "high")
        self.assertEqual(recommendation["status"], "warning")
        self.assertEqual(recommendation["actionType"], "disease")
        self.assertTrue(recommendation["nextStep"])
        self.assertIn("причини", recommendation["summary"])
        self.assertTrue(recommendation["generatedAt"])

    def test_watering_recommendation_interprets_short_interval_as_attention(self):
        recommendation = PlantRecommendationService().generate(
            plant_name="Cherry",
            plant_date=None,
            action_type="watering",
            note="Повторний полив",
            last_actions=[
                {"action_type": "watering", "date": "2026-04-17", "has_photo": False},
                {"action_type": "watering", "date": "2026-04-16", "has_photo": False},
            ],
            has_photo=False,
            use_ai=False,
        )

        self.assertEqual(recommendation["severity"], "medium")
        self.assertEqual(recommendation["status"], "attention")
        self.assertIn("перезволоження", recommendation["title"].lower())
        self.assertIn("ґрунт", recommendation["nextStep"])

    def test_note_recommendation_raises_attention_for_problem_signals(self):
        recommendation = PlantRecommendationService().generate(
            plant_name="Cherry",
            plant_date=None,
            action_type="note",
            note="На листі з'явилися жовті плями",
            last_actions=[
                {"action_type": "note", "date": "2026-04-17", "has_photo": False},
            ],
            has_photo=False,
            use_ai=False,
        )

        self.assertEqual(recommendation["severity"], "medium")
        self.assertEqual(recommendation["status"], "attention")
        self.assertIn("ознаки", recommendation["title"].lower())

    def test_photo_recommendation_does_not_claim_visual_analysis(self):
        recommendation = PlantRecommendationService().generate(
            plant_name="Cherry",
            plant_date=None,
            action_type="photo",
            note="",
            last_actions=[
                {"action_type": "photo", "date": "2026-04-17", "has_photo": True},
            ],
            has_photo=True,
            use_ai=False,
        )

        self.assertIn("не дає автоматичного діагнозу", recommendation["summary"])
        self.assertIn("Порівняй це фото", recommendation["nextStep"])

    def test_generate_uses_fallback_when_ai_is_unavailable(self):
        service = PlantRecommendationService()
        service.request_ai_recommendation = lambda **kwargs: None

        recommendation = service.generate(
            plant_name="Cherry",
            plant_date=None,
            action_type="pest",
            note="Помітили шкідника",
            last_actions=[],
            has_photo=False,
            use_ai=True,
        )

        self.assertEqual(recommendation["severity"], "high")
        self.assertEqual(recommendation["status"], "warning")
        self.assertEqual(recommendation["actionType"], "pest")

    def test_generate_uses_ai_response_when_available(self):
        service = PlantRecommendationService()
        service.request_ai_recommendation = lambda **kwargs: {
            "severity": "medium",
            "status": "attention",
            "title": "AI title",
            "summary": "AI summary",
            "details": "AI details",
            "nextStep": "AI next step",
        }

        recommendation = service.generate(
            plant_name="Cherry",
            plant_date=None,
            action_type="watering",
            note="Оновили полив",
            last_actions=[],
            has_photo=False,
            use_ai=True,
        )

        self.assertEqual(recommendation["severity"], "medium")
        self.assertEqual(recommendation["status"], "attention")
        self.assertEqual(recommendation["title"], "AI title")
        self.assertEqual(recommendation["summary"], "AI summary")
        self.assertEqual(recommendation["details"], "AI details")
        self.assertEqual(recommendation["nextStep"], "AI next step")

    def test_ai_cannot_remove_required_context_or_invent_rule_ids(self):
        service = PlantRecommendationService()
        service.request_ai_recommendation = lambda **kwargs: {
            "severity": "medium",
            "status": "attention",
            "title": "AI title",
            "summary": "AI summary",
            "details": "AI details",
            "nextStep": "AI next step",
            "matchedRuleIds": ["invented_rule_01"],
            "confidence": "high",
            "needsMoreData": False,
            "missingData": [],
            "clarifyingQuestion": "",
            "sourceBasis": ["вигадане джерело"],
        }

        recommendation = service.generate(
            plant_name="Огірок",
            plant_date=None,
            action_type="disease",
            note="Листя жовтіє",
            last_actions=[],
            has_photo=False,
            use_ai=True,
        )

        self.assertEqual(recommendation["matchedRuleIds"], [])
        self.assertTrue(recommendation["needsMoreData"])
        self.assertIn("фото листя зверху і знизу", recommendation["missingData"])
        self.assertTrue(recommendation["clarifyingQuestion"])
        self.assertEqual(recommendation["sourceBasis"], ["журнал дій користувача"])


class ProfileDiaryDetailRecommendationTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = Category.objects.create(slug="basil", value="Базилік")

    def test_detail_context_contains_recommendation_for_latest_action(self):
        diary = Diary.objects.create(
            user=self.user,
            title="Cherry",
            description="desc",
            plant_type="tomatoes",
        )
        plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        diary.plants.add(plant)
        DiaryItem.objects.create(
            diary=diary,
            action_type="watering",
            description="Сьогодні підлили",
        )
        latest_item = DiaryItem.objects.create(
            diary=diary,
            action_type="pest",
            description="Помітили шкідника",
            apply_to_all=False,
        )
        latest_item.plants.set([plant])

        response = self.client.get(diary.get_profile_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"][0], latest_item)
        self.assertEqual(response.context["recommendation"]["severity"], "high")
        self.assertEqual(response.context["recommendation"]["status"], "warning")
        self.assertEqual(response.context["recommendation"]["actionType"], "pest")
        self.assertTrue(response.context["recommendation"]["needsMoreData"])
        self.assertContains(response, "Потрібне уточнення:")
        self.assertContains(response, "фото листя зверху і знизу")
        self.assertEqual(response.context["recommendation_target_label"], plant.display_name)

    def test_detail_uses_cached_recommendation_for_latest_action(self):
        diary = Diary.objects.create(
            user=self.user,
            title="Cherry",
            description="desc",
            plant_type="tomatoes",
        )
        plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        diary.plants.add(plant)
        latest_item = DiaryItem.objects.create(
            diary=diary,
            action_type="watering",
            description="Сьогодні підлили",
        )
        latest_item.plants.set([plant])
        session = self.client.session
        session[f"plant_recommendation:{diary.id}"] = {
            "item_id": latest_item.id,
            "recommendation": {
                "severity": "medium",
                "status": "attention",
                "title": "Cached title",
                "summary": "Cached summary",
                "details": "Cached details",
                "nextStep": "Cached next step",
                "actionType": "watering",
                "generatedAt": "17.04.2026 12:00",
            },
        }
        session.save()

        response = self.client.get(diary.get_profile_absolute_url())

        self.assertEqual(response.context["recommendation"]["title"], "Cached title")

    def test_detail_recommendation_target_for_multiple_plants(self):
        diary = Diary.objects.create(user=self.user, title="Beds", description="desc")
        first_plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        second_plant = Plant.objects.create(user=self.user, category=self.category, variety="Thai")
        diary.plants.set([first_plant, second_plant])
        latest_item = DiaryItem.objects.create(
            diary=diary,
            action_type="watering",
            description="Полив",
            apply_to_all=False,
        )
        latest_item.plants.set([first_plant, second_plant])

        response = self.client.get(diary.get_profile_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["recommendation_target_label"],
            f"{first_plant.display_name}, {second_plant.display_name}",
        )

    def test_detail_recommendation_target_for_apply_to_all(self):
        diary = Diary.objects.create(user=self.user, title="Beds", description="desc")
        first_plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        second_plant = Plant.objects.create(user=self.user, category=self.category, variety="Thai")
        diary.plants.set([first_plant, second_plant])
        latest_item = DiaryItem.objects.create(
            diary=diary,
            action_type="watering",
            description="Полив",
            apply_to_all=True,
        )
        latest_item.plants.set([first_plant, second_plant])

        response = self.client.get(diary.get_profile_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["recommendation_target_label"], "усіх активних рослин")

    def test_detail_recommendation_target_respects_selected_plant_filter(self):
        diary = Diary.objects.create(user=self.user, title="Beds", description="desc")
        first_plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        second_plant = Plant.objects.create(user=self.user, category=self.category, variety="Thai")
        diary.plants.set([first_plant, second_plant])
        latest_item = DiaryItem.objects.create(
            diary=diary,
            action_type="watering",
            description="Полив",
            apply_to_all=True,
        )
        latest_item.plants.set([first_plant, second_plant])

        response = self.client.get(diary.get_profile_absolute_url(), {"plant": first_plant.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["recommendation_target_label"], first_plant.display_name)


# Create your tests here.
