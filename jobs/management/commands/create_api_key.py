from django.core.management.base import BaseCommand

from jobs.models import APIKey


class Command(BaseCommand):
    help = "Create an API key. The raw key is printed once and never stored."

    def add_arguments(self, parser):
        parser.add_argument("name", help="Who or what this key is for")

    def handle(self, *args, name, **options):
        _, raw_key = APIKey.generate(name)
        self.stdout.write(self.style.SUCCESS(f"API key for {name!r} (save it now, it won't be shown again):"))
        self.stdout.write(raw_key)
