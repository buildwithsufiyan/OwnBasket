from django.core.management.base import BaseCommand

from fonts.services import (
    bootstrap_typography_catalog,
)


class Command(BaseCommand):
    help = 'Seed the default Canva-style starter font library.'

    def handle(self, *args, **options):
        bootstrap_typography_catalog()
        self.stdout.write(self.style.SUCCESS('Default font library, Google typography catalog, and font packs have been seeded.'))
