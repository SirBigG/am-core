import xlrd

from django.core.management.base import BaseCommand

from core.classifier.models import Region, Country

from transliterate import translit


class Command(BaseCommand):

    def handle(self, *args, **options):
        rb = xlrd.open_workbook('Ukrainian_cities.xls', formatting_info=True)
        sheet = rb.sheet_by_index(0)
        l = list()
        for rownum in range(1, sheet.nrows):
            row = sheet.row_values(rownum)
            i, title = row
            l.append(Region(id=int(i), value=title, slug=translit(title.lower(), 'uk', reversed=True),
                            country=Country.objects.get(slug='ukraine')))

        Region.objects.bulk_create(l)
        self.stdout.write(self.style.SUCCESS('Loaded: %s' % len(l)))
