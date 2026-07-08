from django.core.management.base import BaseCommand

from themes.services import scan_theme_packages


class Command(BaseCommand):
    help = "Scan theme package folders and register valid themes in the database."

    def handle(self, *args, **options):
        results = scan_theme_packages()
        created_count = 0
        updated_count = 0
        invalid_count = 0

        for result in results:
            if result.errors:
                invalid_count += 1
                self.stdout.write(self.style.ERROR(f"Invalid theme: {result.folder_name}"))
                for error in result.errors:
                    self.stdout.write(self.style.ERROR(f"  - {error}"))
                continue

            if result.created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Added theme: {result.theme.name}"))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f"Updated theme: {result.theme.name}"))

            for warning in result.warnings:
                self.stdout.write(self.style.WARNING(f"  - {warning}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(self.style.SUCCESS("Scan Complete"))
        self.stdout.write(self.style.SUCCESS(f"New Themes Added: {created_count}"))
        self.stdout.write(self.style.SUCCESS(f"Themes Updated: {updated_count}"))
        self.stdout.write(self.style.SUCCESS(f"Invalid Themes: {invalid_count}"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
