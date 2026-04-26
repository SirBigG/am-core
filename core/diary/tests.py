from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.classifier.models import Category
from core.diary.forms import DiaryForm, DiaryItemForm, PlantAttachmentFormSet, save_diary_plants
from core.diary.models import Diary, DiaryItem, Plant
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
        Diary.objects.filter(pk=older_diary.pk).update(updated=timezone.datetime(2026, 4, 24, tzinfo=timezone.utc))
        Diary.objects.filter(pk=newer_diary.pk).update(updated=timezone.datetime(2026, 4, 25, tzinfo=timezone.utc))

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


class ProfileDiaryDetailFilterTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = Category.objects.create(slug="basil", value="Базилік")
        self.diary = Diary.objects.create(user=self.user, title="Diary", description="desc")
        self.first_plant = Plant.objects.create(user=self.user, category=self.category, variety="Genovese")
        self.second_plant = Plant.objects.create(user=self.user, category=self.category, variety="Thai")
        self.diary.plants.set([self.first_plant, self.second_plant])

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

    def test_filter_events_by_plant(self):
        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"plant": self.first_plant.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"], [self.first_item])
        self.assertEqual(response.context["selected_plant_id"], str(self.first_plant.pk))

    def test_search_events_by_description(self):
        response = self.client.get(
            self.diary.get_profile_absolute_url(),
            {"q": "тайського"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"], [self.second_item])
        self.assertEqual(response.context["event_search_query"], "тайського")


class DiaryFormPlantTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.request = type("Request", (), {"user": self.user})()
        self.species_parent = Category.objects.create(
            slug="plants",
            value="Рослини",
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

    def test_category_picker_only_shows_children_of_diary_species_parent(self):
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
        self.assertEqual(
            response.json()["results"],
            [{"id": str(self.active_plant.pk), "text": str(self.active_plant)}],
        )


class DiaryItemFormPlantTargetTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
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

        self.assertEqual(
            list(form.initial["plants"]),
            [self.active_plant, self.second_active_plant],
        )

    def test_save_without_selected_plants_applies_to_all_active_plants(self):
        form = DiaryItemForm(
            diary=self.diary,
            data={
                "action_type": "note",
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

        self.assertEqual(list(item.plants.all()), [self.second_active_plant])

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

    def test_searches_active_plants(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("diaries:plant-autocomplete") + "?q=geno")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["results"],
            [{"id": str(self.active_plant.pk), "text": str(self.active_plant)}],
        )


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

    def test_detail_context_contains_recommendation_for_latest_action(self):
        diary = Diary.objects.create(
            user=self.user,
            title="Cherry",
            description="desc",
            plant_type="tomatoes",
        )
        DiaryItem.objects.create(
            diary=diary,
            action_type="watering",
            description="Сьогодні підлили",
        )
        latest_item = DiaryItem.objects.create(
            diary=diary,
            action_type="pest",
            description="Помітили шкідника",
        )

        response = self.client.get(diary.get_profile_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["diary_items"][0], latest_item)
        self.assertEqual(response.context["recommendation"]["severity"], "high")
        self.assertEqual(response.context["recommendation"]["status"], "warning")
        self.assertEqual(response.context["recommendation"]["actionType"], "pest")

    def test_detail_uses_cached_recommendation_for_latest_action(self):
        diary = Diary.objects.create(
            user=self.user,
            title="Cherry",
            description="desc",
            plant_type="tomatoes",
        )
        latest_item = DiaryItem.objects.create(
            diary=diary,
            action_type="watering",
            description="Сьогодні підлили",
        )
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


# Create your tests here.
