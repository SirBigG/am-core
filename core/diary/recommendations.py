import json
import logging
import re
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags

from core.classifier.models import CategoryAIProfile

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

RULE_SECTION_LABELS = {
    "trigger": "trigger",
    "additional signals": "additionalSignals",
    "known signals": "knownSignals",
    "assumption": "assumption",
    "outcome": "outcome",
    "confidence": "confidence",
    "severity": "severity",
    "recommendation": "recommendation",
    "do not recommend": "doNotRecommend",
    "source / basis": "sourceBasis",
}

KNOWLEDGE_SECTION_KEYWORDS = {
    "watering": ("полив", "мульч", "типові проблем", "severity", "priority"),
    "fertilizer": ("добрив", "живлен", "типові проблем", "severity", "priority"),
    "planted": ("умови вирощування", "посад", "посів", "пророст", "календар", "помилки"),
    "transplanted": ("умови вирощування", "посад", "пересад", "коренева", "помилки"),
    "disease": ("типові проблем", "хвороб", "severity", "priority", "безпек"),
    "pest": ("типові проблем", "шкідник", "severity", "priority", "безпек"),
    "pruning": ("обріз", "формув", "типові проблем"),
    "harvest": ("збір урожаю", "зберігання", "плодонош", "severity", "priority"),
    "photo": ("типові проблем", "хвороб", "шкідник", "severity", "priority"),
    "note": ("типові проблем", "хвороб", "шкідник", "severity", "priority"),
}

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
Використовуй фактичні твердження про культуру лише з plantKnowledge у payload.
Не став остаточний діагноз, якщо даних недостатньо. У такому разі познач needsMoreData=true.
Якщо needsMoreData=true, постав одне коротке уточнювальне питання у clarifyingQuestion.
Не супереч recommendation та doNotRecommend зі знайдених правил.
Якщо matchedRules порожній, дай обережну загальну пораду без вигаданих деталей про культуру.

Поверни JSON об'єкт з полями:
- severity: low | medium | high
- status: ok | attention | warning
- title: короткий змістовний заголовок
- summary: 1-2 короткі речення з висновком
- details: розширене пояснення
- nextStep: одна коротка конкретна порада
- matchedRuleIds: масив Rule ID, на яких базується відповідь
- confidence: low | medium | high
- needsMoreData: true | false
- missingData: масив коротких назв відсутніх даних
- clarifyingQuestion: одне коротке питання або порожній рядок
- sourceBasis: масив коротких назв правил або джерел, на яких базується відповідь

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


def parsePlantRecommendationRules(rules_text):
    """Parse the existing human-readable admin format without rewriting its meaning."""
    blocks = re.split(r"(?im)^\s*Rule ID:\s*$", rules_text or "")
    parsed_rules = []

    for block in blocks[1:]:
        lines = [line.rstrip() for line in block.strip().splitlines()]
        rule_id = next((line.strip() for line in lines if line.strip()), "")
        if not rule_id:
            continue

        sections = {"id": rule_id}
        current_key = None
        current_lines = []

        def save_section():
            if current_key:
                sections[current_key] = "\n".join(line for line in current_lines if line.strip()).strip()

        for line in lines[1:]:
            normalized_label = line.strip().rstrip(":").lower()
            next_key = RULE_SECTION_LABELS.get(normalized_label)
            if next_key:
                save_section()
                current_key = next_key
                current_lines = []
                continue
            if current_key:
                current_lines.append(line.strip())
        save_section()

        known_signals = sections.get("knownSignals", "")
        sections["noteSignals"] = re.findall(
            r'user_note_contains\s*:\s*["“](.+?)["”]',
            known_signals,
            flags=re.IGNORECASE,
        )
        parsed_rules.append(sections)

    if parsed_rules:
        return parsed_rules

    return _parse_legacy_ukrainian_recommendation_rules(rules_text)


def _parse_legacy_ukrainian_recommendation_rules(rules_text):
    """Parse the earlier `Якщо`/`Тоді` rule format used by existing profiles."""
    rule_id_pattern = re.compile(r"(?m)^\s*([a-z][a-z0-9]*(?:_[a-z0-9]+){2,})\s*$")
    matches = list(rule_id_pattern.finditer(rules_text or ""))
    parsed_rules = []

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(rules_text or "")
        block = (rules_text or "")[match.end() : end]
        if_match = re.search(r"(?ims)^\s*Якщо:\s*(.*?)(?=^\s*Тоді:)", block)
        then_match = re.search(r"(?im)^\s*Тоді:\s*(.+?)\s*$", block)
        confidence_match = re.search(r"(?im)^\s*Confidence:\s*(.+?)\s*$", block)
        explanation_match = re.search(r"(?im)^\s*Пояснення:\s*(.+?)\s*$", block)
        recommendation_match = re.search(r"(?im)^\s*Рекомендація:\s*(.+?)\s*$", block)

        if not if_match or not recommendation_match:
            continue

        trigger_lines = [
            line.strip().rstrip(";.")
            for line in if_match.group(1).splitlines()
            if line.strip().rstrip(";.")
        ]
        parsed_rules.append(
            {
                "id": match.group(1),
                "trigger": "\n".join(trigger_lines),
                "noteSignals": trigger_lines,
                "outcome": then_match.group(1).strip() if then_match else "",
                "confidence": confidence_match.group(1).strip() if confidence_match else "",
                "assumption": explanation_match.group(1).strip() if explanation_match else "",
                "recommendation": recommendation_match.group(1).strip(),
            }
        )

    return parsed_rules


def selectRelevantRecommendationRules(rules, *, action_type, note, last_actions=None, limit=3):
    normalized_note = _normalize_match_text(note)
    last_actions = last_actions or []
    scored_rules = []

    for index, rule in enumerate(rules):
        rule_id = rule.get("id", "").lower()
        matched_signals = [
            signal
            for signal in rule.get("noteSignals", [])
            if _signal_matches_note(signal, normalized_note)
        ]
        matched_conditions = _match_rule_history_conditions(
            rule,
            action_type=action_type,
            last_actions=last_actions,
        )
        if not matched_signals and not matched_conditions:
            continue

        score = len(matched_signals) * 10 + len(matched_conditions) * 8

        if action_type and action_type.lower() in rule_id:
            score += 3
        if action_type in {"disease", "photo", "note"} and any(
            keyword in rule_id for keyword in ("mildew", "wilt", "diagnosis", "disease")
        ):
            score += 1
        if action_type == "watering" and any(keyword in rule_id for keyword in ("watering", "water", "moisture")):
            score += 2
        if action_type == "pest" and any(keyword in rule_id for keyword in ("pest", "aphid", "beetle", "mite")):
            score += 2

        scored_rules.append(
            (
                score,
                -index,
                {
                    **rule,
                    "matchedSignals": matched_signals,
                    "matchedConditions": matched_conditions,
                },
            )
        )

    scored_rules.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [rule for _, _, rule in scored_rules[:limit]]


def selectRelevantKnowledgeSections(content, *, action_type, max_chars=5500):
    sections = _split_numbered_sections(content)
    if not sections:
        return (content or "")[:max_chars]

    keywords = KNOWLEDGE_SECTION_KEYWORDS.get(action_type, KNOWLEDGE_SECTION_KEYWORDS["note"])
    selected = []
    for section in sections:
        normalized_title = section["title"].lower()
        if section["number"] == "1" or any(keyword in normalized_title for keyword in keywords):
            selected.append(section["text"])

    return "\n\n".join(selected)[:max_chars]


def buildPlantKnowledgeContext(*, plants, action_type, note, last_actions=None):
    category_ids = {plant.category_id for plant in plants or [] if plant.category_id}
    if not category_ids:
        return []

    profiles = (
        CategoryAIProfile.objects.filter(
            category_id__in=category_ids,
            status=CategoryAIProfile.STATUS_READY,
            is_ai_enabled=True,
        )
        .select_related("category")
        .only(
            "category_id",
            "title",
            "content",
            "recommendation_rules",
            "sources",
            "category__value",
            "category__slug",
        )
        .order_by("category__value")
    )
    contexts = []
    for profile in profiles:
        parsed_rules = parsePlantRecommendationRules(profile.recommendation_rules)
        matched_rules = selectRelevantRecommendationRules(
            parsed_rules,
            action_type=action_type,
            note=note,
            last_actions=last_actions,
        )
        contexts.append(
            {
                "categoryId": profile.category_id,
                "category": profile.category.value,
                "categorySlug": profile.category.slug,
                "profileTitle": profile.title or profile.category.value,
                "knowledge": selectRelevantKnowledgeSections(profile.content, action_type=action_type),
                "matchedRules": [_serialize_rule_for_prompt(rule) for rule in matched_rules],
                "sources": profile.sources,
            }
        )
    return contexts


def preparePlantRecommendationPayload(
    *,
    plant_name,
    plant_date,
    action_type,
    note,
    last_actions,
    has_photo,
    plant_knowledge=None,
    plants=None,
):
    normalized_note = _normalize_note(note)
    latest_action_date = last_actions[0].get("date") if last_actions else None

    return {
        "plantName": plant_name,
        "plantDate": plant_date.isoformat() if plant_date else None,
        "plants": [_serialize_plant_context(plant) for plant in plants or []],
        "latestAction": {
            "actionType": action_type,
            "actionLabel": ACTION_LABELS.get(action_type, action_type or "Дія"),
            "date": latest_action_date,
        },
        "note": normalized_note,
        "lastActions": [_serialize_action_context(action) for action in last_actions[:10]],
        "recentActivity": _build_recent_activity(last_actions),
        "hasPhoto": has_photo,
        "plantKnowledge": plant_knowledge or [],
        "matchedRuleIds": [
            rule["id"]
            for profile in plant_knowledge or []
            for rule in profile.get("matchedRules", [])
        ],
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

    def generate(
        self,
        *,
        plant_name,
        plant_date,
        action_type,
        note,
        last_actions,
        has_photo,
        plants=None,
        use_ai=False,
    ):
        plant_knowledge = buildPlantKnowledgeContext(
            plants=plants or [],
            action_type=action_type,
            note=note,
            last_actions=last_actions,
        )
        payload = preparePlantRecommendationPayload(
            plant_name=plant_name,
            plant_date=plant_date,
            action_type=action_type,
            note=note,
            last_actions=last_actions,
            has_photo=has_photo,
            plant_knowledge=plant_knowledge,
            plants=plants,
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
            "max_output_tokens": getattr(settings, "PLANT_RECOMMENDATION_OPENAI_MAX_OUTPUT_TOKENS", 420),
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
                            "matchedRuleIds": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                            "needsMoreData": {"type": "boolean"},
                            "missingData": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "clarifyingQuestion": {"type": "string"},
                            "sourceBasis": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "severity",
                            "status",
                            "title",
                            "summary",
                            "details",
                            "nextStep",
                            "matchedRuleIds",
                            "confidence",
                            "needsMoreData",
                            "missingData",
                            "clarifyingQuestion",
                            "sourceBasis",
                        ],
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
        matched_rules = _flatten_matched_rules(payload)
        if matched_rules:
            primary_rule = matched_rules[0]
            if primary_rule.get("recommendation"):
                rule_based_recommendation["nextStep"] = _first_sentence(primary_rule["recommendation"])
            if primary_rule.get("assumption"):
                rule_based_recommendation["details"] = " ".join(
                    part
                    for part in (
                        rule_based_recommendation.get("details", ""),
                        f"Профіль культури: {primary_rule['assumption']}",
                    )
                    if part
                )
        rule_based_recommendation["actionType"] = action_type
        rule_based_recommendation["matchedRuleIds"] = payload.get("matchedRuleIds", [])
        rule_based_recommendation["confidence"] = _normalize_confidence(
            matched_rules[0].get("confidence") if matched_rules else "low"
        )
        missing_data = _build_missing_data(payload, matched_rules)
        rule_based_recommendation["needsMoreData"] = bool(missing_data)
        rule_based_recommendation["missingData"] = missing_data
        rule_based_recommendation["clarifyingQuestion"] = _build_clarifying_question(missing_data)
        rule_based_recommendation["sourceBasis"] = _build_source_basis(payload, matched_rules)
        rule_severity = _infer_matched_rule_severity(matched_rules)
        if rule_severity:
            rule_based_recommendation["severity"] = rule_severity
            rule_based_recommendation["status"] = STATUS_BY_SEVERITY[rule_severity]
        rule_based_recommendation["generatedAt"] = timezone.localtime().strftime("%d.%m.%Y %H:%M")
        return rule_based_recommendation

    def _merge_ai_recommendation(self, payload, ai_recommendation):
        fallback_recommendation = self._build_fallback_recommendation(payload)
        missing_data = _unique_strings(
            [
                *fallback_recommendation["missingData"],
                *ai_recommendation.get("missingData", []),
            ]
        )
        needs_more_data = bool(missing_data) or ai_recommendation.get("needsMoreData", False)
        allowed_rule_ids = set(payload.get("matchedRuleIds", []))
        ai_rule_ids = [
            rule_id
            for rule_id in ai_recommendation.get("matchedRuleIds", [])
            if rule_id in allowed_rule_ids
        ]
        return {
            "severity": ai_recommendation.get("severity") or fallback_recommendation["severity"],
            "status": ai_recommendation.get("status") or fallback_recommendation["status"],
            "title": ai_recommendation.get("title") or fallback_recommendation["title"],
            "summary": ai_recommendation.get("summary") or fallback_recommendation["summary"],
            "details": ai_recommendation.get("details") or fallback_recommendation["details"],
            "nextStep": ai_recommendation.get("nextStep") or fallback_recommendation["nextStep"],
            "matchedRuleIds": ai_rule_ids or fallback_recommendation["matchedRuleIds"],
            "confidence": ai_recommendation.get("confidence") or fallback_recommendation["confidence"],
            "needsMoreData": needs_more_data,
            "missingData": missing_data,
            "clarifyingQuestion": (
                ai_recommendation.get("clarifyingQuestion")
                if needs_more_data and ai_recommendation.get("clarifyingQuestion")
                else _build_clarifying_question(missing_data)
            ),
            "sourceBasis": fallback_recommendation["sourceBasis"],
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


def _normalize_match_text(value):
    return " ".join(strip_tags(value or "").replace("’", "'").lower().split())


def _signal_matches_note(signal, normalized_note):
    normalized_signal = _normalize_match_text(signal)
    if not normalized_signal:
        return False
    return bool(
        re.search(
            rf"(?<!\w){re.escape(normalized_signal)}(?!\w)",
            normalized_note,
            flags=re.UNICODE,
        )
    )


def _split_numbered_sections(content):
    matches = list(re.finditer(r"(?m)^\s*(\d+)\.\s+(.+?)\s*$", content or ""))
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections.append(
            {
                "number": match.group(1),
                "title": match.group(2).strip(),
                "text": (content or "")[match.start() : end].strip(),
            }
        )
    return sections


def _serialize_rule_for_prompt(rule):
    return {
        key: rule.get(key, "")
        for key in (
            "id",
            "trigger",
            "knownSignals",
            "assumption",
            "outcome",
            "confidence",
            "recommendation",
            "doNotRecommend",
            "sourceBasis",
            "severity",
            "matchedSignals",
            "matchedConditions",
        )
        if rule.get(key)
    }


def _flatten_matched_rules(payload):
    return [
        rule
        for profile in payload.get("plantKnowledge", [])
        for rule in profile.get("matchedRules", [])
    ]


def _first_sentence(value):
    compact = " ".join((value or "").split())
    if not compact:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", compact, maxsplit=1)
    return parts[0]


def _normalize_confidence(value):
    normalized = (value or "").strip().lower()
    if "high" in normalized:
        return "high"
    if "medium" in normalized:
        return "medium"
    return "low"


def _normalize_severity(value):
    normalized = (value or "").strip().lower()
    return normalized if normalized in STATUS_BY_SEVERITY else ""


def _serialize_plant_context(plant):
    plant_date = getattr(plant, "plant_date", None)
    age_days = None
    if plant_date:
        age_days = max((timezone.localdate() - plant_date).days, 0)
    category = getattr(plant, "category", None)
    return {
        "id": getattr(plant, "pk", None),
        "category": getattr(category, "value", "") or None,
        "categorySlug": getattr(category, "slug", "") or None,
        "variety": getattr(plant, "variety", "") or None,
        "title": getattr(plant, "title", "") or None,
        "plantDate": plant_date.isoformat() if plant_date else None,
        "ageDays": age_days,
        "growingEnvironment": None,
    }


def _serialize_action_context(action):
    action_type = action.get("action_type") or action.get("actionType")
    return {
        "actionType": action_type,
        "actionLabel": ACTION_LABELS.get(action_type, action_type or "Дія"),
        "date": action.get("date"),
        "note": _normalize_note(action.get("note", "")),
        "hasPhoto": bool(action.get("has_photo") or action.get("hasPhoto")),
    }


def _build_recent_activity(last_actions):
    activity = {}
    for action_type in ("watering", "fertilizer", "disease", "pest"):
        action = next(
            (
                item
                for item in last_actions
                if (item.get("action_type") or item.get("actionType")) == action_type
            ),
            None,
        )
        activity[action_type] = _serialize_action_context(action) if action else None
    return activity


def _match_rule_history_conditions(rule, *, action_type, last_actions):
    condition_text = "\n".join(
        value
        for value in (
            rule.get("trigger", ""),
            rule.get("additionalSignals", ""),
            rule.get("knownSignals", ""),
        )
        if value
    )
    matches = []
    action_conditions = re.findall(
        r"(?:action_type|latest_action)\s*[:=]\s*[\"']?([a-z_]+)",
        condition_text,
        flags=re.IGNORECASE,
    )
    if action_conditions:
        if action_type not in {condition.lower() for condition in action_conditions}:
            return []
        matches.append(f"action_type={action_type}")

    aliases = {
        "watering": "watering",
        "fertilizer": "fertilizer",
    }
    for condition_action, history_action in aliases.items():
        if action_type != condition_action:
            continue
        pattern = re.compile(
            rf"(?:days_since_(?:last|previous)_{history_action}|{history_action}_interval_days)\s*"
            r"(<=|>=|<|>|=)\s*(\d+)",
            flags=re.IGNORECASE,
        )
        interval_conditions = pattern.findall(condition_text)
        if not interval_conditions:
            continue
        days = _days_between_latest_actions(last_actions, history_action)
        if days is None:
            return []
        for operator, raw_threshold in interval_conditions:
            threshold = int(raw_threshold)
            comparisons = {
                "<": days < threshold,
                "<=": days <= threshold,
                ">": days > threshold,
                ">=": days >= threshold,
                "=": days == threshold,
            }
            if not comparisons[operator]:
                return []
            condition_match = f"days_since_previous_{history_action}={days}"
            if condition_match not in matches:
                matches.append(condition_match)
    return matches


def _days_between_latest_actions(last_actions, action_type):
    dates = []
    for action in last_actions:
        if (action.get("action_type") or action.get("actionType")) != action_type:
            continue
        try:
            dates.append(timezone.datetime.fromisoformat(action.get("date", "")).date())
        except (TypeError, ValueError):
            continue
        if len(dates) == 2:
            return (dates[0] - dates[1]).days
    return None


def _build_source_basis(payload, matched_rules):
    sources = []
    for rule in matched_rules:
        source = rule.get("sourceBasis")
        if source and source not in sources:
            sources.append(source)
    if not sources:
        for profile in payload.get("plantKnowledge", []):
            source = (profile.get("sources") or "").strip()
            if source and source not in sources:
                sources.append(source)
    return sources or ["журнал дій користувача"]


def _build_missing_data(payload, matched_rules):
    action_type = payload.get("latestAction", {}).get("actionType")
    note = _normalize_match_text(payload.get("note", ""))
    rule_ids = " ".join(rule.get("id", "") for rule in matched_rules)
    missing_data = []

    diagnosis_context = action_type in {"disease", "pest"} or any(
        keyword in rule_ids
        for keyword in ("mildew", "wilt", "diagnosis", "disease", "pest", "aphid", "beetle")
    )
    needs_photo_by_rule = any(
        "без фото" in _normalize_match_text(rule.get("doNotRecommend", ""))
        or "без огляду" in _normalize_match_text(rule.get("doNotRecommend", ""))
        for rule in matched_rules
    )
    if not payload.get("hasPhoto") and (diagnosis_context or needs_photo_by_rule):
        missing_data.append("фото листя зверху і знизу")

    plants = payload.get("plants", [])
    variety_sensitive = any(keyword in rule_ids for keyword in ("pollination", "parthenocarpic"))
    if variety_sensitive and plants and any(not plant.get("variety") for plant in plants):
        missing_data.append("сорт рослини")

    environment_sensitive = diagnosis_context or any(
        keyword in rule_ids for keyword in ("pollination", "greenhouse", "cold_soil")
    )
    environment_in_note = any(
        keyword in note
        for keyword in ("теплиц", "відкрит", "грунт", "ґрунт", "контейнер", "горщик")
    )
    has_environment = any(plant.get("growingEnvironment") for plant in plants)
    if environment_sensitive and not environment_in_note and not has_environment:
        missing_data.append("середовище вирощування: теплиця чи відкритий ґрунт")

    soil_sensitive = action_type == "watering" or any(
        keyword in rule_ids for keyword in ("watering", "wilt", "diagnosis")
    )
    soil_in_note = any(keyword in note for keyword in ("сух", "мокр", "волог", "перезвол"))
    if soil_sensitive and not soil_in_note:
        missing_data.append("стан ґрунту перед поливом")

    if soil_sensitive and _count_actions(payload, "watering") == 0:
        missing_data.append("дата останнього поливу")

    return _unique_strings(missing_data)[:3]


def _count_actions(payload, action_type):
    return sum(
        action.get("actionType") == action_type
        for action in payload.get("lastActions", [])
    )


def _build_clarifying_question(missing_data):
    if not missing_data:
        return ""
    return "Уточни, будь ласка: {}?".format("; ".join(missing_data))


def _infer_matched_rule_severity(matched_rules):
    if not matched_rules:
        return ""
    explicit_severity = _normalize_severity(matched_rules[0].get("severity"))
    if explicit_severity:
        return explicit_severity
    rule_id = matched_rules[0].get("id", "").lower()
    if any(keyword in rule_id for keyword in ("bacterial_wilt", "root_rot", "severe", "critical")):
        return "high"
    if any(keyword in rule_id for keyword in ("harvest_young", "succession_sowing")):
        return "low"
    return "medium"


def _unique_strings(values):
    unique = []
    for value in values:
        if isinstance(value, str) and value and value not in unique:
            unique.append(value)
    return unique
