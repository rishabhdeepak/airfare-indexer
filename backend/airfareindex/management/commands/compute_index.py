"""
Management command: python manage.py compute_index

Computes route indices + the national APIx for today's date (or a
specified date), using the earliest scraped date as the base period.
"""

from datetime import date

from django.core.management.base import BaseCommand
from airfareindex.index_engine import compute_and_save_indices_for_date


class Command(BaseCommand):
    help = "Compute the Airfare Price Index for a given date (default: today)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Date to compute index for, YYYY-MM-DD (default: today).",
        )

    def handle(self, *args, **options):
        if options["date"]:
            target_date = date.fromisoformat(options["date"])
        else:
            target_date = date.today()

        result = compute_and_save_indices_for_date(target_date)

        if "error" in result:
            self.stdout.write(self.style.ERROR(result["error"]))
            return

        self.stdout.write(f"\nBase period: {result['base_date']}")
        self.stdout.write(f"Target date: {result['target_date']}\n")
        self.stdout.write("Route indices:")
        for route, idx in result["route_indices"].items():
            self.stdout.write(f"  {route}: {idx:.1f}")
        self.stdout.write(
            self.style.SUCCESS(
                f"\nNational APIx: {result['national_index']:.1f} "
                f"(from {result['routes_included']} routes)"
            )
        )