import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags

from .models import DIARY_ITEM_ACTION_CHOICES


logger = logging.getLogger("django")

STATUS_BY_SEVERITY = {
    "low": "ok",
    "medium": "attention",
    "high": "warning",
}

SEVERITY_BY_ACTION = {
    "watering": "low",
    "fertilizer": "low",
    "photo": "low",
    "note": "low",
    "planted": "low",
    "pruning": "medium",
    "harvest": "medium",
    "disease": "high",
    "pest": "high",
}

ACTION_LABELS = dict(DIARY_ITEM_ACTION_CHOICES)

SEVERITY_META = {
    "low": {
        "title_prefix": "Все йде стабільно",
        "focus": "Продовжуй спостерігати за станом рослини у звичному режимі.",
    },
    "medium": {
        "title_prefix": "Потрібна уважність",
        "focus": "Перевір наступні кілька днів, як рослина реагує на цю дію.",
    },
    "high": {
        "title_prefix": "Потрібна швидка перевірка",
        "focus": "Зафіксуй зміни якнайшвидше і не відкладай наступний огляд.",
    },
}

PLANT_RECOMMENDATION_SYSTEM_PROMPT_TEMPLATE = """
Ти асистент Garden Planner. Твоя задача: після нової дії користувача дати коротку, практичну рекомендацію для конкретної рослини.

Відповідь має пояснювати:
1. що ця дія означає для рослини
2. чи це норма, увага або проблема
3. що робити далі

Не переказуй журнал подій. Не роби головним змістом просте повторення назви дії.
Навіть для звичайних дій дай корисний висновок. Для ризиків будь конкретним і прикладним.
Якщо фото додано без vision-аналізу, не вдавай, що система бачить зображення.

Поверни JSON об'єкт з полями:
- severity: low | medium | high
- status: ok | attention | warning
- title: короткий змістовний заголовок
- summary: 1-2 короткі речення з висновком
- details: розширене пояснення
- nextStep: одна коротка конкретна порада

Правила по типах дій:
- watering: оцінюй інтервал від попереднього поливу, відмічай норму або ризик переливу, радь перевірити вологість ґрунту
- fertilizer: оцінюй доречність і не радь повторювати добриво занадто швидко, особливо після стресу, хвороби чи шкідника
- planted: давай стартову пораду на перші дні після посадки
- note: аналізуй текст; якщо є симптоми або проблемні слова, підвищуй severity
- photo: не стверджуй, що бачиш фото; кажи, що фото допоможе відстежувати зміни, і підкажи що перевірити
- disease: дай 2-3 можливі причини, що перевірити, і першу безпечну дію
- pest: коротко припусти можливу проблему і дай перші дії
- pruning: поясни, що після обрізки треба поспостерігати за відновленням
- harvest: дай нейтральний позитивний висновок і доречний наступний крок
""".strip()

PLANT_RECOMMENDATION_USER_PROMPT_TEMPLATE = """
Підготуй рекомендацію для рослини на основі такого контексту:

{payload}
""".strip()


def preparePlantRecommendationPayload(*, plant_name, plant_date, action_type, note, last_actions, has_photo):
    normalized_note = _normalize_note(note)
    latest_action_date = last_actions[0].get("date") if last_actions else None

    return {
        "plantName": plant_name,
        "plantDate": plant_date.isoformat() if plant_date else None,
        "latestAction": {
            "actionType": action_type,
            "actionLabel": ACTION_LABELS.get(action_type, action_type or "Дія"),
            "date": latest_action_date,
        },
        "note": normalized_note,
        "lastActions": [
            {
                "actionType": action.get("action_type") or action.get("actionType"),
                "actionLabel": ACTION_LABELS.get(
                    action.get("action_type") or action.get("actionType"),
                    action.get("action_type") or action.get("actionType") or "Дія",
                ),
                "date": action.get("date"),
                "hasPhoto": bool(action.get("has_photo") or action.get("hasPhoto")),
            }
            for action in last_actions[:5]
        ],
        "hasPhoto": has_photo,
        "preparedAt": timezone.localtime().isoformat(),
    }


def buildPlantRecommendationSystemPrompt():
    return PLANT_RECOMMENDATION_SYSTEM_PROMPT_TEMPLATE


def buildPlantRecommendationUserPrompt(payload):
    return PLANT_RECOMMENDATION_USER_PROMPT_TEMPLATE.format(
        payload=json.dumps(payload, ensure_ascii=False, indent=2)
    )


class PlantRecommendationService:
    session_key_prefix = "plant_recommendation"

    def generate(self, *, plant_name, plant_date, action_type, note, last_actions, has_photo, use_ai=False):
        payload = preparePlantRecommendationPayload(
            plant_name=plant_name,
            plant_date=plant_date,
            action_type=action_type,
            note=note,
            last_actions=last_actions,
            has_photo=has_photo,
        )
        system_prompt = buildPlantRecommendationSystemPrompt()
        user_prompt = buildPlantRecommendationUserPrompt(payload)

        fallback_recommendation = self._build_fallback_recommendation(payload)

        if not use_ai:
            return fallback_recommendation

        try:
            ai_recommendation = self.request_ai_recommendation(
                payload=payload,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception:
            logger.exception("Plant recommendation AI request failed")
            return fallback_recommendation

        if not ai_recommendation:
            return fallback_recommendation

        return self._merge_ai_recommendation(payload, ai_recommendation)

    def request_ai_recommendation(self, *, payload, system_prompt, user_prompt):
        logger.info("Prepared plant recommendation payload: %s", json.dumps(payload, ensure_ascii=False))
        logger.info("Prepared plant recommendation system prompt: %s", system_prompt)
        logger.info("Prepared plant recommendation user prompt: %s", user_prompt)

        api_key = getattr(settings, "PLANT_RECOMMENDATION_OPENAI_API_KEY", "")
        if not api_key:
            return None

        request_body = {
            "model": getattr(settings, "PLANT_RECOMMENDATION_OPENAI_MODEL", "gpt-4.1-mini"),
            "instructions": system_prompt,
            "input": user_prompt,
            "max_output_tokens": getattr(settings, "PLANT_RECOMMENDATION_OPENAI_MAX_OUTPUT_TOKENS", 220),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "plant_recommendation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "severity": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                            "status": {
                                "type": "string",
                                "enum": ["ok", "attention", "warning"],
                            },
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                            "details": {"type": "string"},
                            "nextStep": {"type": "string"},
                        },
                        "required": ["severity", "status", "title", "summary", "details", "nextStep"],
                    },
                }
            },
        }
        request_data = json.dumps(request_body).encode("utf-8")
        request = urllib.request.Request(
            getattr(settings, "PLANT_RECOMMENDATION_OPENAI_URL", "https://api.openai.com/v1/responses"),
            data=request_data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=getattr(settings, "PLANT_RECOMMENDATION_OPENAI_TIMEOUT", 8),
            ) as response:
                raw_response = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            logger.warning("Plant recommendation AI HTTP error: %s", exc.read().decode("utf-8", errors="ignore"))
            return None
        except urllib.error.URLError:
            logger.exception("Plant recommendation AI URL error")
            return None

        response_data = json.loads(raw_response)
        parsed_recommendation = self._extract_response_json(response_data)
        logger.info("Plant recommendation AI response: %s", json.dumps(parsed_recommendation, ensure_ascii=False))
        return parsed_recommendation

    def build_cached_recommendation(self, request, *, diary_id, item_id, fallback_recommendation):
        cached_recommendation = self.get_cached_recommendation(request, diary_id=diary_id, item_id=item_id)
        return cached_recommendation or fallback_recommendation

    def cache_recommendation(self, request, *, diary_id, item_id, recommendation):
        request.session[self._build_session_key(diary_id)] = {
            "item_id": item_id,
            "recommendation": recommendation,
        }
        request.session.modified = True

    def get_cached_recommendation(self, request, *, diary_id, item_id):
        session_payload = request.session.get(self._build_session_key(diary_id))
        if not session_payload:
            return None
        if session_payload.get("item_id") != item_id:
            return None
        return session_payload.get("recommendation")

    def clear_cached_recommendation(self, request, *, diary_id):
        session_key = self._build_session_key(diary_id)
        if session_key in request.session:
            del request.session[session_key]
            request.session.modified = True

    def _build_fallback_recommendation(self, payload):
        action_type = payload["latestAction"]["actionType"]
        rule_based_recommendation = self._build_rule_based_recommendation(payload)
        rule_based_recommendation["actionType"] = action_type
        rule_based_recommendation["generatedAt"] = timezone.localtime().strftime("%d.%m.%Y %H:%M")
        return rule_based_recommendation

    def _merge_ai_recommendation(self, payload, ai_recommendation):
        fallback_recommendation = self._build_fallback_recommendation(payload)
        return {
            "severity": ai_recommendation.get("severity") or fallback_recommendation["severity"],
            "status": ai_recommendation.get("status") or fallback_recommendation["status"],
            "title": ai_recommendation.get("title") or fallback_recommendation["title"],
            "summary": ai_recommendation.get("summary") or fallback_recommendation["summary"],
            "details": ai_recommendation.get("details") or fallback_recommendation["details"],
            "nextStep": ai_recommendation.get("nextStep") or fallback_recommendation["nextStep"],
            "actionType": payload["latestAction"]["actionType"],
            "generatedAt": timezone.localtime().strftime("%d.%m.%Y %H:%M"),
        }

    def _extract_response_json(self, response_data):
        output_items = response_data.get("output", [])
        for item in output_items:
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return json.loads(content["text"])
        return None

    def _build_rule_based_recommendation(self, payload):
        action_type = payload["latestAction"]["actionType"]
        handler = getattr(self, "_recommend_for_{}".format(action_type), self._recommend_default)
        recommendation = handler(payload)
        recommendation["status"] = recommendation.get("status") or STATUS_BY_SEVERITY[recommendation["severity"]]
        return recommendation

    def _recommend_for_watering(self, payload):
        days_since_previous = self._days_since_previous_action(payload, "watering")
        if days_since_previous is None:
            return {
                "severity": "low",
                "status": "ok",
                "title": "Полив виглядає доречним",
                "summary": "Для рослини це нормальний сигнал підтримки після чергового догляду. Зараз важливо не поспішати з наступним поливом.",
                "details": "Без попереднього інтервалу краще орієнтуватися не на календар, а на фактичну вологість ґрунту і стан листя. Надлишок води ризикованіший за коротку паузу.",
                "nextStep": "Перед наступним поливом перевір верхній шар ґрунту пальцем.",
            }
        if days_since_previous <= 1:
            return {
                "severity": "medium",
                "status": "attention",
                "title": "Є ризик перезволоження",
                "summary": "Полив стався доволі швидко після попереднього, тому рослині важливіше просохнути, ніж отримати ще воду. Це не обов'язково проблема, але тут потрібна обережність.",
                "details": "Частий полив може дати млявість, пожовтіння або навантаження на коріння, особливо якщо ґрунт ще вологий. Далі варто дивитися на стан субстрату, а не повторювати полив за інерцією.",
                "nextStep": "Зроби паузу і перевір вологість ґрунту перед будь-яким новим поливом.",
            }
        return {
            "severity": "low",
            "status": "ok",
            "title": "Режим поливу виглядає рівним",
            "summary": "За інтервалом це схоже на нормальний догляд без явного ризику переливу. Тепер краще просто поспостерігати, як рослина тримає тургор і колір листя.",
            "details": "Якщо після цього поливу листя залишається пружним, а ґрунт просихає поступово, режим можна вважати стабільним. Наступні рішення краще приймати за станом ґрунту і погодою.",
            "nextStep": "Спостерігай за ґрунтом і не поливай повторно, поки верхній шар не підсохне.",
        }

    def _recommend_for_fertilizer(self, payload):
        recent_stress = self._has_recent_problem_action(payload)
        if recent_stress:
            return {
                "severity": "medium",
                "status": "attention",
                "title": "Після стресу з добривом потрібна обережність",
                "summary": "Добриво не завжди допомагає, якщо рослина нещодавно мала ознаки хвороби або шкідника. У такому стані важливіше стабілізувати рослину, ніж підсилювати ріст.",
                "details": "Ослаблена рослина може гірше переносити додаткове живлення, особливо якщо причина проблеми ще не усунута. Спершу краще оцінити відновлення листя, темп росту і загальний стан.",
                "nextStep": "Найближчими днями не додавай ще добриво і спостерігай за реакцією рослини.",
            }
        return {
            "severity": "low",
            "status": "ok",
            "title": "Підживлення виглядає доречним",
            "summary": "Для активної рослини це може бути нормальна підтримка росту, якщо вона не має явного стресу. Тепер головне не дублювати підживлення занадто швидко.",
            "details": "Після внесення добрива корисно спостерігати, чи зберігається рівний колір листя і чи немає ознак підпалу або в'ялості. Часті повтори зазвичай шкодять більше, ніж помірна пауза.",
            "nextStep": "Зараз лише спостерігай і не внось нову порцію добрива найближчим часом.",
        }

    def _recommend_for_planted(self, payload):
        return {
            "severity": "low",
            "status": "ok",
            "title": "Рослина входить у період адаптації",
            "summary": "Після посадки найважливіші перші дні, коли коріння звикає до нового місця. Тут нормальні спокійний полив, м'який режим і уважне спостереження.",
            "details": "У цей період варто стежити, чи не падає тургор, чи не пересихає ґрунт і чи немає різкого стресу від сонця або холоду. Головна задача зараз не стимулювати ріст, а дати рослині спокійно вкоренитися.",
            "nextStep": "Перевір вологість ґрунту і стан листя в найближчі 2-3 дні.",
        }

    def _recommend_for_note(self, payload):
        if self._note_has_problem_signal(payload["note"]):
            return {
                "severity": "medium",
                "status": "attention",
                "title": "У нотатці є ознаки можливої проблеми",
                "summary": "Опис схожий не просто на нейтральне спостереження, а на сигнал, який варто перевірити окремо. Поки це ще не обов'язково проблема, але ігнорувати таку нотатку не варто.",
                "details": "Слова про плями, пожовтіння, в'ялість, гниль або шкідників зазвичай означають, що рослині потрібен додатковий огляд. Важливо уточнити, де саме з'явився симптом і чи він посилюється.",
                "nextStep": "Оглянь листя і стебло ближче та зафіксуй, чи симптом посилюється.",
            }
        return {
            "severity": "low",
            "status": "ok",
            "title": "Нотатка корисна для спостереження",
            "summary": "Запис виглядає як нормальна фіксація стану без явного ризику. Це допоможе відстежити зміни в динаміці, якщо щось піде не так пізніше.",
            "details": "Нейтральні нотатки особливо корисні як точка порівняння для наступних днів. Вони дозволяють помітити, коли стан рослини реально змінюється, а не здається іншим випадково.",
            "nextStep": "Порівняй стан рослини з цією нотаткою через кілька днів.",
        }

    def _recommend_for_photo(self, payload):
        return {
            "severity": "low",
            "status": "ok",
            "title": "Фото стало доброю точкою відліку",
            "summary": "Саме фото ще не дає автоматичного діагнозу, але воно допоможе побачити зміни в листі, стеблі або плодах пізніше. Це корисно для спокійного спостереження без поспішних висновків.",
            "details": "Без візуального аналізу не варто робити вигляд, що проблема вже визначена. Найбільша цінність фото зараз у тому, що його можна буде порівняти з наступними записами й побачити прогрес або погіршення.",
            "nextStep": "Порівняй це фото з наступним через кілька днів і зверни увагу на колір та форму листя.",
        }

    def _recommend_for_disease(self, payload):
        return {
            "severity": "high",
            "status": "warning",
            "title": "Симптоми схожі на реальну проблему",
            "summary": "Для рослини це вже не просто звичайне спостереження, а сигнал ризику, який краще перевірити швидко. Найчастіші причини тут: перезволоження, грибкове ураження або стрес від температури й вентиляції.",
            "details": "Спершу варто подивитися, де саме з'явились симптоми: на нижньому листі, по краях, у плямах чи на стеблі. Безпечно почати з ізоляції підозрілих частин, контролю вологи, провітрювання і перевірки, чи не мокне листя занадто довго.",
            "nextStep": "Оглянь уражені ділянки, прибери сильно пошкоджене листя і зменш вологість навколо рослини.",
        }

    def _recommend_for_pest(self, payload):
        return {
            "severity": "high",
            "status": "warning",
            "title": "Є ризик активного ураження шкідником",
            "summary": "Для рослини це потенційно швидка проблема, бо шкідники часто поширюються ще до явного погіршення стану. Тут важливі не спостереження в загальному, а перші конкретні дії.",
            "details": "Найчастіше варто перевірити нижній бік листя, молоді пагони і точки росту, де ховаються дрібні комахи або липкий наліт. Безпечний перший крок це механічний огляд, ізоляція рослини і локальне очищення уражених місць.",
            "nextStep": "Перевір нижній бік листя і ізолюй рослину від інших на час огляду.",
        }

    def _recommend_for_pruning(self, payload):
        return {
            "severity": "medium",
            "status": "attention",
            "title": "Після обрізки важливий період спостереження",
            "summary": "Обрізка може допомогти рослині, але далі треба дивитися, як вона відновлюється без зайвого стресу. Найкращий сценарій зараз це спокійний догляд і контроль реакції.",
            "details": "Після обрізки рослина може коротко пригальмувати ріст, тому не варто одразу навантажувати її частими поливами або підживленням. Добрий знак це пружне листя, рівний колір і відсутність підсихання зрізів.",
            "nextStep": "Спостерігай за зрізами та загальним станом листя кілька днів без різких змін у догляді.",
        }

    def _recommend_for_harvest(self, payload):
        return {
            "severity": "low",
            "status": "ok",
            "title": "Рослина дійшла до продуктивної фази",
            "summary": "Збір урожаю виглядає як нормальний позитивний етап, а не сигнал проблеми. Після цього корисно оцінити, чи рослина продовжує цвісти й формувати нові плоди.",
            "details": "Після збору врожаю рослина часто переходить у наступний цикл плодоношення або поступово сповільнюється. Тут важливо спостерігати за новими зав'язями, станом листя і загальним виснаженням куща.",
            "nextStep": "Перевір, чи з'являються нові зав'язі або чи потрібен м'який підтримувальний догляд.",
        }

    def _recommend_default(self, payload):
        severity = SEVERITY_BY_ACTION.get(payload["latestAction"]["actionType"], "low")
        severity_meta = SEVERITY_META[severity]
        return {
            "severity": severity,
            "status": STATUS_BY_SEVERITY[severity],
            "title": f"{severity_meta['title_prefix']} для {payload['plantName']}",
            "summary": "Остання дія виглядає як частина нормального догляду, але її варто оцінювати через подальший стан рослини.",
            "details": severity_meta["focus"],
            "nextStep": "Спостерігай за рослиною і зафіксуй наступну зміну стану.",
        }

    def _build_session_key(self, diary_id):
        return f"{self.session_key_prefix}:{diary_id}"

    def _days_since_previous_action(self, payload, action_type):
        previous_date = None
        for action in payload["lastActions"][1:]:
            if action.get("actionType") == action_type and action.get("date"):
                previous_date = action["date"]
                break
        latest_date = payload["latestAction"].get("date")
        if not latest_date or not previous_date:
            return None
        try:
            return (timezone.datetime.fromisoformat(latest_date).date() - timezone.datetime.fromisoformat(previous_date).date()).days
        except ValueError:
            return None

    def _has_recent_problem_action(self, payload):
        for action in payload["lastActions"][1:4]:
            if action.get("actionType") in {"disease", "pest"}:
                return True
        return False

    def _note_has_problem_signal(self, note):
        lowered_note = (note or "").lower()
        problem_keywords = [
            "плям",
            "жовт",
            "в'ял",
            "вял",
            "сохн",
            "гни",
            "хвор",
            "шкід",
            "комах",
            "дірк",
            "наліт",
            "пліс",
            "чорн",
            "скруч",
        ]
        return any(keyword in lowered_note for keyword in problem_keywords)


def _normalize_note(note):
    cleaned_note = strip_tags(note or "").replace("\xa0", " ").strip()
    if not cleaned_note:
        return ""
    compact_note = " ".join(cleaned_note.split())
    if len(compact_note) <= 140:
        return compact_note
    return f"{compact_note[:137]}..."
