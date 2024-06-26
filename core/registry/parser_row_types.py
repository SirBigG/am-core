from collections import namedtuple

ActiveRegistryItem = namedtuple(
    "ActiveRegistryItem",
    [
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
        "registration_year",
        "patent",
        "creation_method",
        "recommended_zone",
        "direction_of_use",
        "ripeness_group",
        "quality",
        "variety_vailabl",
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
    ],
)


InactiveRegistryItem = namedtuple(
    "ActiveRegistryItem",
    [
        "end_date",
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
        "registration_year",
        "patent",
        "creation_method",
        "recommended_zone",
        "direction_of_use",
        "ripeness_group",
        "quality",
        "variety_vailabl",
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
    ],
)
