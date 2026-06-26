import re

from core.classifier.models import CategoryAIProfile

SPACING_KEYWORDS = (
    "відстан",
    "схема посад",
    "між рослин",
    "між ряд",
    "густот",
    "spacing",
)
MEASUREMENT_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?(?:\s*[–—-]\s*\d+(?:[.,]\d+)?)?\s*(?:см|cm|мм|mm|м|m)\b", re.IGNORECASE)


def extract_planner_spacing_guidance(plant, limit=3):
    """Return confirmed spacing lines from the ready admin AI profile."""
    if not plant.category_id:
        return {"items": [], "source": ""}

    profile = getattr(plant.category, "ai_profile", None)
    if (
        profile is None
        or profile.status != CategoryAIProfile.STATUS_READY
        or not profile.is_ai_enabled
    ):
        return {"items": [], "source": ""}

    candidates = []
    for raw_line in (profile.content or "").splitlines():
        line = re.sub(r"^\s*(?:[-*+]\s+|#{1,6}\s+|\d+[.)]\s+)", "", raw_line).strip()
        normalized = line.lower()
        if not line or len(line) > 320:
            continue
        if not any(keyword in normalized for keyword in SPACING_KEYWORDS):
            continue
        if not MEASUREMENT_PATTERN.search(normalized):
            continue
        if line not in candidates:
            candidates.append(line)
        if len(candidates) >= limit:
            break

    return {
        "items": candidates,
        "source": profile.title or f"AI-профіль: {plant.category.value}",
    }
