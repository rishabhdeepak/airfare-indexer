"""
Management command: python manage.py run_scraper

Interactively asks which routes and booking windows to scrape, runs the
scraper, and saves every result straight into the database.
"""

import asyncio
import sys
import os

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date, parse_datetime

from ingestion.scrapers.spicejet import scrape_multiple
from airfareindex.models import FareObservation


class Command(BaseCommand):
    help = "Interactively scrape SpiceJet fares for user-chosen routes and load them into the database."

    def handle(self, *args, **options):
        routes = self.prompt_for_routes()
        if not routes:
            self.stdout.write(self.style.WARNING("No routes entered. Exiting."))
            return

        booking_windows = self.prompt_for_booking_windows()

        self.stdout.write(
            f"\nScraping {len(routes)} route(s) x {len(booking_windows)} booking window(s)..."
        )
        records = asyncio.run(scrape_multiple(routes, booking_windows))
        self.stdout.write(f"Scraped {len(records)} records. Saving to database...")

        saved = 0
        for r in records:
            FareObservation.objects.create(
                origin=r["origin"],
                destination=r["destination"],
                flight_date=parse_date(r["flight_date"]),
                airline=r["airline"],
                flight_number=r.get("flight_number"),
                advance_days=r["advance_days"],
                base_fare=r["base_fare"],
                taxes=r["taxes"],
                fees=r["fees"],
                total_fare=r["total_fare"],
                source=r["source"],
                scraped_at=parse_datetime(r["timestamp"]),
            )
            saved += 1

        self.stdout.write(self.style.SUCCESS(f"Saved {saved} records to the database."))

    def prompt_for_routes(self):
        self.stdout.write("\nEnter routes to scrape, one per line as 'ORIGIN DESTINATION' (e.g. DEL BOM).")
        self.stdout.write("Press Enter on an empty line when you're done.\n")

        routes = []
        while True:
            line = input(f"Route {len(routes) + 1} (or Enter to finish): ").strip().upper()
            if not line:
                break

            parts = line.split()
            if len(parts) != 2:
                self.stdout.write(self.style.WARNING("  Enter exactly two airport codes, e.g. 'DEL BOM'. Try again."))
                continue

            origin, destination = parts
            if len(origin) != 3 or len(destination) != 3:
                self.stdout.write(self.style.WARNING("  Airport codes should be 3 letters, e.g. 'DEL BOM'. Try again."))
                continue
            if origin == destination:
                self.stdout.write(self.style.WARNING("  Origin and destination can't be the same. Try again."))
                continue

            routes.append((origin, destination))
            self.stdout.write(self.style.SUCCESS(f"  Added {origin} -> {destination}"))

        return routes

    def prompt_for_booking_windows(self):
        default = [1, 7, 15, 30, 45]
        self.stdout.write(f"\nBooking windows (days ahead) to check. Default: {default}")
        line = input("Enter comma-separated days, or press Enter for default: ").strip()

        if not line:
            return default
        try:
            windows = [int(x.strip()) for x in line.split(",") if x.strip()]
            return windows if windows else default
        except ValueError:
            self.stdout.write(self.style.WARNING("Couldn't parse that — using default."))
            return default