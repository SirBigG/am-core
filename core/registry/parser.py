import logging
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree
from zipfile import ZipFile

import requests
from django.db import transaction
from django.utils.translation import get_language
from openpyxl import load_workbook
from transliterate import slugify

from .models import Company, Country, Variety, VarietyCategory
from .parser_row_types import (
    ActiveRegistryItem,
    InactiveRegistryItem,
    normalize_active_registry_row,
    normalize_inactive_registry_row,
)

logger = logging.getLogger("django")

file_path = "media/registry_2026_06_29.xlsx"

ODS_NAMESPACES = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
}
ODS_MAX_COLUMNS = 64


class RegistryWorksheet:
    def __init__(self, title, rows):
        self.title = title
        self.rows = rows
        self.max_row = len(rows)

    def iter_rows(self, min_row=1, max_row=None, values_only=True):
        if not values_only:
            raise ValueError("RegistryWorksheet only supports values_only=True.")
        max_row = max_row or self.max_row
        for row in self.rows[min_row - 1 : max_row]:
            yield tuple(row)


def parse_registry_date(value):
    if not value:
        return None, None
    if isinstance(value, datetime):
        return value.date(), value.year
    if isinstance(value, date):
        return value, value.year
    try:
        value = datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        value = datetime.strptime(value, "%Y-%m-%d").date()
    return value, value.year


def get_repeated_count(element, attribute):
    value = element.attrib.get(f"{{{ODS_NAMESPACES['table']}}}{attribute}")
    return int(value) if value else 1


def get_ods_cell_value(cell):
    value_type = cell.attrib.get(f"{{{ODS_NAMESPACES['office']}}}value-type")
    if value_type == "float":
        value = cell.attrib.get(f"{{{ODS_NAMESPACES['office']}}}value")
        if value is None:
            return None
        number = float(value)
        return int(number) if number.is_integer() else number
    if value_type == "date":
        return cell.attrib.get(f"{{{ODS_NAMESPACES['office']}}}date-value")
    value = "".join(cell.itertext())
    return value if value != "" else None


def read_ods_worksheets(path):
    worksheets = []
    table_tag = f"{{{ODS_NAMESPACES['table']}}}table"
    row_tag = f"{{{ODS_NAMESPACES['table']}}}table-row"
    cell_tags = {
        f"{{{ODS_NAMESPACES['table']}}}table-cell",
        f"{{{ODS_NAMESPACES['table']}}}covered-table-cell",
    }
    with ZipFile(path) as archive:
        with archive.open("content.xml") as content:
            context = ElementTree.iterparse(content, events=("start", "end"))
            current_sheet = None
            current_rows = None
            current_row = None
            for event, element in context:
                if event == "start" and element.tag == table_tag:
                    current_sheet = element.attrib.get(f"{{{ODS_NAMESPACES['table']}}}name", "")
                    current_rows = []
                    continue
                if current_rows is None:
                    continue
                if event == "start" and element.tag == row_tag:
                    current_row = []
                    continue
                if event == "end" and element.tag in cell_tags and current_row is not None:
                    repeated = get_repeated_count(element, "number-columns-repeated")
                    value = get_ods_cell_value(element)
                    if value is not None or len(current_row) < ODS_MAX_COLUMNS:
                        current_row.extend([value] * min(repeated, ODS_MAX_COLUMNS - len(current_row)))
                    element.clear()
                    continue
                if event == "end" and element.tag == row_tag:
                    if current_row and any(value not in (None, "") for value in current_row):
                        repeated = get_repeated_count(element, "number-rows-repeated")
                        current_rows.extend([current_row] * repeated)
                    current_row = None
                    element.clear()
                    continue
                if event == "end" and element.tag == table_tag:
                    worksheets.append(RegistryWorksheet(current_sheet, current_rows))
                    current_sheet = None
                    current_rows = None
                    element.clear()
    return worksheets


def load_registry_worksheets(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".ods":
        return read_ods_worksheets(path)
    workbook = load_workbook(filename=path)
    return workbook.worksheets


def import_registry_workbook(path, *, api=False, token=None, start_row=2):
    def run_import():
        return {
            "applicants": parse_applicant(api=api, token=token, start_row=start_row, workbook_path=path),
            "owners": parse_owner(api=api, token=token, start_row=start_row, workbook_path=path),
            "breeders": parse_breeder(api=api, token=token, start_row=start_row, workbook_path=path),
            "active_varieties": parse_varieties(api=api, token=token, start_row=start_row, workbook_path=path),
            "inactive_varieties": parse_inactive_varieties(
                api=api, token=token, start_row=start_row, workbook_path=path
            ),
        }

    if api:
        return run_import()
    with transaction.atomic():
        return run_import()


def import_uploaded_registry_file(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in {".xlsx", ".ods"}:
        raise ValueError("Upload an .xlsx or .ods registry file.")
    with NamedTemporaryFile(suffix=suffix) as temporary_file:
        for chunk in uploaded_file.chunks():
            temporary_file.write(chunk)
        temporary_file.flush()
        return import_registry_workbook(temporary_file.name)


def parse_company(worksheet_number, api: bool = False, token: str = None, start_row: int = 2, workbook_path=None):
    worksheets = load_registry_worksheets(workbook_path or file_path)
    sheet = worksheets[worksheet_number]
    row_count = sheet.max_row
    counter = start_row - 1
    processed_count = 0
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {token}"})
    for row in sheet.iter_rows(min_row=start_row, max_row=sheet.max_row, values_only=True):
        if api:
            # send POST request to API
            response = session.post(
                "https://agromega.in.ua/api/registry/add-company/",
                json={"row": row},
                timeout=10,
            )
            if response.status_code != 200:
                logger.error(f"Error while sending data to API: {response.text}")
            counter += 1
            processed_count += 1
            logger.info(f"Row {counter} of {row_count} sent to API")
            continue
        Company.save_company_from_row(row)
        processed_count += 1
    return processed_count


def parse_applicant(api: bool = False, token: str = None, start_row: int = 2, workbook_path=None):
    return parse_company(2, api, token, start_row, workbook_path=workbook_path)


def parse_owner(api: bool = False, token: str = None, start_row: int = 2, workbook_path=None):
    return parse_company(3, api, token, start_row, workbook_path=workbook_path)


def parse_breeder(api: bool = False, token: str = None, start_row: int = 2, workbook_path=None):
    return parse_company(4, api, token, start_row, workbook_path=workbook_path)


def parse_varieties(api: bool = False, token: str = None, start_row: int = 2, workbook_path=None):
    countries = {country["short_slug"]: country["id"] for country in Country.objects.values("short_slug", "id")}
    companies = {company["code"]: company["id"] for company in Company.objects.values("code", "id")}
    base_categories = {
        category["title"]: category["id"] for category in VarietyCategory.objects.filter(level=1).values("title", "id")
    }
    children_categories = {
        category["title"]: category["id"] for category in VarietyCategory.objects.filter(level=2).values("title", "id")
    }
    worksheets = load_registry_worksheets(workbook_path or file_path)
    sheet = worksheets[0]
    row_count = sheet.max_row
    counter = start_row - 1
    processed_count = 0
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {token}"})
    for row in sheet.iter_rows(min_row=start_row, max_row=sheet.max_row, values_only=True):
        row = normalize_active_registry_row(row)
        if api:
            # send POST request to API
            response = session.post(
                "https://agromega.in.ua/api/registry/add-active-variety/",
                json={"row": row},
                timeout=10,
            )
            if response.status_code != 200:
                logger.error(f"Error while sending data to API: {response.text}")
            counter += 1
            processed_count += 1
            logger.info(f"Row {counter} of {row_count} sent to API")
            continue
        item = ActiveRegistryItem._make(row)
        base_category_title = item.base_category_title
        if base_category_title not in base_categories:
            # Check if category already exists
            slug = slugify(base_category_title, get_language())
            base_category = VarietyCategory.objects.filter(slug=slug).first()
            if base_category is None:
                base_category = VarietyCategory.objects.create(title=base_category_title)
                base_category.save()
            base_categories[base_category_title] = base_category.id
        base_category_id = base_categories[base_category_title]
        children_category_title = item.child_category_title
        if children_category_title not in children_categories:
            # Check if category already exists
            slug = slugify(children_category_title, get_language())
            children_category = VarietyCategory.objects.filter(slug=slug).first()
            if children_category is None:
                children_category = VarietyCategory.objects.create(
                    title=children_category_title, parent_id=base_category_id
                )
                children_category.save()
            children_categories[children_category_title] = children_category.id
        children_category_id = children_categories[children_category_title]
        title = item.title
        registration_country = item.registration_country
        if registration_country:
            registration_country = countries.get(item.registration_country.lower(), None)
        original_country = item.original_country
        if original_country:
            original_country = countries.get(item.original_country.lower(), None)
        if Variety.objects.filter(title=title, category_id=children_category_id).exists():
            Variety.objects.filter(title=title, category_id=children_category_id).update(
                title_original=item.title_original,
                application_number=item.application_number,
                registration_year=item.registration_year,
                recommended_zone=item.recommended_zone,
                direction_of_use=item.direction_of_use,
                ripeness_group=item.ripeness_group,
                quality=item.quality,
                registration_country_id=registration_country,
                original_country_id=original_country,
                applicant_id=companies.get(item.applicant, None),
                applicant2_id=companies.get(item.applicant2, None),
                owner_id=companies.get(item.owner, None),
                owner2_id=companies.get(item.owner2, None),
                breeder_id=companies.get(item.breeder, None),
                unregister_date=None,
                unregister_year=None,
                excluded=False,
            )
            processed_count += 1
            continue
        variety = Variety.objects.create(
            title=title,
            title_original=item.title_original,
            application_number=item.application_number,
            registration_year=item.registration_year,
            recommended_zone=item.recommended_zone,
            direction_of_use=item.direction_of_use,
            ripeness_group=item.ripeness_group,
            quality=item.quality,
            registration_country_id=registration_country,
            original_country_id=original_country,
            applicant_id=companies.get(item.applicant, None),
            applicant2_id=companies.get(item.applicant2, None),
            owner_id=companies.get(item.owner, None),
            owner2_id=companies.get(item.owner2, None),
            breeder_id=companies.get(item.breeder, None),
            category_id=children_category_id,
        )
        variety.save()
        processed_count += 1
    return processed_count


def parse_inactive_varieties(api: bool = False, token: str = None, start_row: int = 2, workbook_path=None):
    countries = {country["short_slug"]: country["id"] for country in Country.objects.values("short_slug", "id")}
    companies = {company["code"]: company["id"] for company in Company.objects.values("code", "id")}
    base_categories = {
        category["title"]: category["id"] for category in VarietyCategory.objects.filter(level=1).values("title", "id")
    }
    children_categories = {
        category["title"]: category["id"] for category in VarietyCategory.objects.filter(level=2).values("title", "id")
    }
    worksheets = load_registry_worksheets(workbook_path or file_path)
    sheet = worksheets[1]
    row_count = sheet.max_row
    counter = start_row - 1
    processed_count = 0
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {token}"})
    for row in sheet.iter_rows(min_row=start_row, max_row=sheet.max_row, values_only=True):
        row = normalize_inactive_registry_row(row)
        if api:
            # send POST request to API
            response = session.post(
                "https://agromega.in.ua/api/registry/add-inactive-variety/",
                json={"row": row},
                headers={"Authorization": f"Token {token}"},
                timeout=10,
            )
            if response.status_code != 200:
                logger.error(f"Error while sending data to API: {response.text}")
            counter += 1
            processed_count += 1
            logger.info(f"Row {counter} of {row_count} sent to API")
            continue
        item = InactiveRegistryItem._make(row)
        end_date, end_date_year = parse_registry_date(item.end_date)
        base_category_title = item.base_category_title
        if base_category_title not in base_categories:
            # Check if category already exists
            slug = slugify(base_category_title, get_language())
            base_category = VarietyCategory.objects.filter(slug=slug).first()
            if base_category is None:
                base_category = VarietyCategory.objects.create(title=base_category_title)
                base_category.save()
            base_categories[base_category_title] = base_category.id
        base_category_id = base_categories[base_category_title]
        children_category_title = item.child_category_title
        if children_category_title not in children_categories:
            # Check if category already exists
            slug = slugify(children_category_title, get_language())
            children_category = VarietyCategory.objects.filter(slug=slug).first()
            if children_category is None:
                children_category = VarietyCategory.objects.create(
                    title=children_category_title, parent_id=base_category_id
                )
                children_category.save()
            children_categories[children_category_title] = children_category.id
        children_category_id = children_categories[children_category_title]
        title = item.title
        registration_country = item.registration_country
        if registration_country:
            registration_country = countries.get(item.registration_country.lower(), None)
        original_country = item.original_country
        if original_country:
            original_country = countries.get(item.original_country.lower(), None)
        if Variety.objects.filter(title=title, category_id=children_category_id).exists():
            Variety.objects.filter(title=title, category_id=children_category_id).update(
                title_original=item.title_original,
                application_number=item.application_number,
                registration_year=item.registration_year,
                recommended_zone=item.recommended_zone,
                direction_of_use=item.direction_of_use,
                ripeness_group=item.ripeness_group,
                quality=item.quality,
                registration_country_id=registration_country,
                original_country_id=original_country,
                applicant_id=companies.get(item.applicant, None),
                applicant2_id=companies.get(item.applicant2, None),
                owner_id=companies.get(item.owner, None),
                owner2_id=companies.get(item.owner2, None),
                breeder_id=companies.get(item.breeder, None),
                unregister_date=end_date,
                unregister_year=end_date_year,
                excluded=True,
            )
            processed_count += 1
            continue
        variety = Variety.objects.create(
            title=title,
            title_original=item.title_original,
            application_number=item.application_number,
            registration_year=item.registration_year,
            recommended_zone=item.recommended_zone,
            direction_of_use=item.direction_of_use,
            ripeness_group=item.ripeness_group,
            quality=item.quality,
            registration_country_id=registration_country,
            original_country_id=original_country,
            applicant_id=companies.get(item.applicant, None),
            applicant2_id=companies.get(item.applicant2, None),
            owner_id=companies.get(item.owner, None),
            owner2_id=companies.get(item.owner2, None),
            breeder_id=companies.get(item.breeder, None),
            category_id=children_category_id,
            unregister_date=end_date,
            unregister_year=end_date_year,
            excluded=True,
        )
        variety.save()
        processed_count += 1
    return processed_count
