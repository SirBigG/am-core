import xlrd

from django.core.management.base import BaseCommand

from core.classifier.models import Location, Country

from transliterate import translit


class Command(BaseCommand):

    def handle(self, *args, **options):
        uk = Country.objects.get(slug='ukraine')
        rb = xlrd.open_workbook('Ukrainian_cities.xls', formatting_info=True)
        sheet = rb.sheet_by_index(2)
        l = list()
        for rownum in range(1, sheet.nrows):
            row = sheet.row_values(rownum)
            i, region_id, area_id, title, s, la, lo, a = row
            l.append(Location(id=int(i), country=uk, region_id=region_id,
                              area_id=area_id, value=title,
                              slug=translit(title.lower(), 'uk', reversed=True)))

        Location.objects.bulk_create(l)
        self.stdout.write(self.style.SUCCESS('Loaded: %s' % len(l)))
