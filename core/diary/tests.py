from django.test import TestCase

from core.diary.models import Diary, DiaryItem
from core.diary.recommendations import (
    PlantRecommendationService,
    buildPlantRecommendationSystemPrompt,
    buildPlantRecommendationUserPrompt,
    preparePlantRecommendationPayload,
)
from core.utils.tests.factories import UserFactory


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
        session["plant_recommendation:{}".format(diary.id)] = {
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
