APPLE_VARIETY_PARENT_SLUG = "yabluni"
APPLE_VARIETY_RUBRIC_SLUG = "sorty-yablun"

APPLE_VARIETY_ATTRIBUTE_GROUPS = (
    {
        "title": "Термін дозрівання",
        "fields": (
            {
                "key": "ripening_period",
                "label": "Термін дозрівання",
                "multiple": False,
                "choices": (
                    ("early", "ранній"),
                    ("summer", "літній"),
                    ("mid_season", "середнього строку"),
                    ("autumn", "осінній"),
                    ("late", "пізній"),
                    ("late_autumn", "пізньоосінній"),
                    ("winter", "зимовий"),
                    ("late_winter", "пізньозимовий"),
                ),
            },
        ),
    },
    {
        "title": "Плоди",
        "fields": (
            {
                "key": "fruit_color",
                "label": "Колір плодів",
                "multiple": True,
                "choices": (
                    ("red", "червоний"),
                    ("green", "зелений"),
                    ("yellow", "жовтий"),
                    ("pink", "рожевий"),
                    ("striped_marble", "смугастий/мармуровий"),
                    ("blush", "з рум'янцем"),
                ),
            },
            {
                "key": "fruit_size",
                "label": "Розмір плодів",
                "multiple": False,
                "choices": (
                    ("small", "дрібний/невеликий"),
                    ("medium", "середній"),
                    ("large", "великий"),
                    ("very_large", "великий/дуже великий"),
                ),
            },
        ),
    },
    {
        "title": "Смак і використання",
        "fields": (
            {
                "key": "taste",
                "label": "Смак",
                "multiple": True,
                "choices": (
                    ("sweet", "солодкий"),
                    ("sweet_tart", "кисло-солодкий"),
                    ("tart", "кислий/з кислинкою"),
                    ("dessert", "десертний"),
                    ("aromatic", "ароматний"),
                    ("astringent", "з терпкістю"),
                ),
            },
            {
                "key": "use",
                "label": "Призначення",
                "multiple": True,
                "choices": (
                    ("fresh", "свіже споживання"),
                    ("storage", "зберігання"),
                    ("juice", "сік"),
                    ("drying", "сушіння"),
                    ("baking", "випічка/кулінарія"),
                    ("processing", "переробка/універсальне"),
                ),
            },
            {
                "key": "keeping",
                "label": "Лежкість",
                "multiple": False,
                "choices": (
                    ("short", "коротке зберігання"),
                    ("medium", "середня або добра лежкість"),
                    ("long", "довге зберігання / до весни"),
                ),
            },
        ),
    },
    {
        "title": "Дерево і врожай",
        "fields": (
            {
                "key": "tree_type",
                "label": "Тип дерева / росту",
                "multiple": True,
                "choices": (
                    ("vigorous", "сильнорослий"),
                    ("medium_vigor", "середньорослий"),
                    ("low_vigor", "слаборослий/низькорослий"),
                    ("dwarf_rootstock", "карликова підщепа"),
                    ("semi_dwarf_rootstock", "напівкарликова підщепа"),
                    ("columnar", "колоновидний"),
                ),
            },
            {
                "key": "yielding",
                "label": "Урожайність / плодоношення",
                "multiple": True,
                "choices": (
                    ("high_yield", "високоврожайний"),
                    ("regular_bearing", "стабільне плодоношення"),
                    ("biennial_bearing", "періодичне плодоношення"),
                    ("precocious", "скороплідний"),
                ),
            },
        ),
    },
    {
        "title": "Стійкість і запилення",
        "fields": (
            {
                "key": "resistance",
                "label": "Стійкість",
                "multiple": True,
                "choices": (
                    ("winter_hardy", "зимостійкий/морозостійкий"),
                    ("scab_resistant", "стійкість до парші"),
                    ("powdery_mildew_resistant", "стійкість до борошнистої роси/цвілі"),
                    ("disease_resistant", "загальна стійкість до хвороб"),
                    ("scab_susceptible", "чутливий до парші"),
                ),
            },
            {
                "key": "pollination",
                "label": "Запилення",
                "multiple": False,
                "choices": (
                    ("self_fertile", "самоплідний"),
                    ("partially_self_fertile", "частково самоплідний"),
                    ("needs_pollinator", "потребує запилювача"),
                    ("good_pollinator", "добрий запилювач"),
                ),
            },
        ),
    },
)


APPLE_VARIETY_ATTRIBUTE_FIELDS = tuple(
    field
    for group in APPLE_VARIETY_ATTRIBUTE_GROUPS
    for field in group["fields"]
)


def apple_attribute_form_field_name(key):
    return f"apple_attribute_{key}"
