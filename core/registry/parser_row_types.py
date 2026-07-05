from collections import namedtuple

ACTIVE_REGISTRY_ITEM_FIELDS = [
    "base_category_title",
    "base_category_title_en",
    "child_category_title",
    "child_category_title_en",
    "child_category_title_lt",
    "application_number",
    "date",
    "title",
    "title_original",
    "title_translit",
    "selection_number",
    "registration_year",
    "certificate_number",
    "patent",
    "creation_method",
    "recommended_zone",
    "direction_of_use",
    "ripeness_group",
    "quality",
    "variety_description",
    "eu_upov_description",
    "variety_status",
    "original_country",
    "registration_country",
    "applicant",
    "applicant2",
    "applicant3",
    "applicant4",
    "applicant5",
    "applicant6",
    "owner",
    "owner2",
    "owner3",
    "owner4",
    "owner5",
    "owner6",
    "breeder",
    "breeder2",
    "breeder3",
    "breeder4",
    "breeder5",
    "breeder6",
]

ACTIVE_REGISTRY_ITEM_OLD_COLUMN_COUNT = 38
ACTIVE_REGISTRY_ITEM_COLUMN_COUNT = len(ACTIVE_REGISTRY_ITEM_FIELDS)

ActiveRegistryItem = namedtuple("ActiveRegistryItem", ACTIVE_REGISTRY_ITEM_FIELDS)


INACTIVE_REGISTRY_ITEM_FIELDS = ["end_date"] + ACTIVE_REGISTRY_ITEM_FIELDS
INACTIVE_REGISTRY_ITEM_OLD_COLUMN_COUNT = ACTIVE_REGISTRY_ITEM_OLD_COLUMN_COUNT + 1
INACTIVE_REGISTRY_ITEM_COLUMN_COUNT = len(INACTIVE_REGISTRY_ITEM_FIELDS)

InactiveRegistryItem = namedtuple("InactiveRegistryItem", INACTIVE_REGISTRY_ITEM_FIELDS)


def normalize_active_registry_row(row):
    row = list(row)
    if len(row) == ACTIVE_REGISTRY_ITEM_OLD_COLUMN_COUNT:
        row = row[:10] + [None] + row[10:11] + [None] + row[11:17] + [None, None] + row[17:]
    if len(row) < ACTIVE_REGISTRY_ITEM_COLUMN_COUNT:
        row += [None for _ in range(ACTIVE_REGISTRY_ITEM_COLUMN_COUNT - len(row))]
    return row[:ACTIVE_REGISTRY_ITEM_COLUMN_COUNT]


def normalize_inactive_registry_row(row):
    row = list(row)
    if len(row) == INACTIVE_REGISTRY_ITEM_OLD_COLUMN_COUNT:
        row = row[:11] + [None] + row[11:12] + [None] + row[12:18] + [None, None] + row[18:]
    if len(row) < INACTIVE_REGISTRY_ITEM_COLUMN_COUNT:
        row += [None for _ in range(INACTIVE_REGISTRY_ITEM_COLUMN_COUNT - len(row))]
    return row[:INACTIVE_REGISTRY_ITEM_COLUMN_COUNT]
