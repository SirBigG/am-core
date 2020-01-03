import xlrd

from django.core.management.base import BaseCommand

from core.classifier.models import Area

from transliterate import translit


class Command(BaseCommand):

    def handle(self, *args, **options):
        rb = xlrd.open_workbook('Ukrainian_cities.xls', formatting_info=True)
        sheet = rb.sheet_by_index(1)
        list_ = list()
        for rownum in range(1, sheet.nrows):
            row = sheet.row_values(rownum)
            i, region_id, title = row
            list_.append(Area(id=int(i), value=title, slug=translit(title.lower(), 'uk', reversed=True),
                              region_id=region_id))

        Area.objects.bulk_create(list_)
        self.stdout.write(self.style.SUCCESS('Loaded: %s' % len(list_)))
