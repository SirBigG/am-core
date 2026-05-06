from datetime import timezone as dt_timezone

from django.test import TestCase
from django.urls import reverse
from django.utils.formats import date_format
from django.utils import timezone

from core.classifier.models import Category
from core.diary.forms import (
    PLANT_BLOCKED_TEXT,
    DiaryForm,
    DiaryItemForm,
    PlantAttachmentFormSet,
    save_diary_plants,
)
from core.diary.models import DIARY_ITEM_ACTION_CHOICES, Diary, DiaryItem, Plant
from core.diary.recommendations import (
    PlantRecommendationService,
    buildPlantRecommendationSystemPrompt,
    buildPlantRecommendationUserPrompt,
    preparePlantRecommendationPayload,
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

    def test_profile_diary_list_prefetches_latest_event(self):
        user = UserFactory()
        diary = Diary.objects.create(user=user, title="Diary", description="desc")
        old_item = DiaryItem.objects.create(diary=diary, action_type="note", date="2026-04-25")
        latest_item = DiaryItem.objects.create(diary=diary, action_type="photo", date="2026-04-26")

        self.client.force_login(user)
        response = self.client.get(reverse("pro_auth:profile-diary-list"))
        listed_diary = response.context["object_list"][0]

        self.assertEqual(listed_diary.latest_diary_items[0], latest_item)
        self.assertEqual(listed_diary.latest_diary_items[1], old_item)

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

        response = self.client.get(
            reverse("pro_auth:profile-diary-item-delete", kwargs={"pk": source_item.pk})
        )

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

        response = self.client.get(
            reverse("pro_auth:profile-diary-item-delete", kwargs={"pk": target_item.pk})
        )

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

        response = self.client.get(reverse("pro_auth:profile-diary-item-delete", kwargs={"pk": latest_finished_item.pk}))

        self.assertEqual(response.status_code, 302)
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.status, "completed")
        self.assertEqual(self.plant.completed_at.isoformat(), "2026-04-20")


class PlantRecommendationServiceTests(TestCase):
    def test_prepare_payload_collects_expected_context(self):
        payload = preparePlantRecommendationPayload(
            plant_name="Cherry",
            plant_date=None,
            action_type="disease",
            note="<p>Плями на листі</p>",
            last_actions=[
                {"action_type": "watering", "date": "2026-04-15", "has_photo": False},
                {"action_type": "photo", "date": "2026-04-16", "has_photo": True},
            ],
            has_photo=True,
        )

        self.assertEqual(payload["plantName"], "Cherry")
        self.assertEqual(payload["latestAction"]["actionType"], "disease")
        self.assertEqual(payload["note"], "Плями на листі")
        self.assertEqual(len(payload["lastActions"]), 2)
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
