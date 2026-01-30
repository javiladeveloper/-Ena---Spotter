import csv
from django.core.management.base import BaseCommand
from fuel_optimizer.models import FuelStation


class Command(BaseCommand):
    help = "Import fuel station data from CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str)
        parser.add_argument("--batch-size", type=int, default=1000)

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        batch_size = options["batch_size"]

        self.stdout.write("Clearing existing fuel station data...")
        FuelStation.objects.all().delete()

        self.stdout.write(f"Reading data from {csv_file}...")

        stations_to_create = []
        seen_entries = set()

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                unique_key = (
                    row["OPIS Truckstop ID"],
                    row["Truckstop Name"],
                    row["Retail Price"],
                )

                if unique_key in seen_entries:
                    continue
                seen_entries.add(unique_key)

                try:
                    price = float(row["Retail Price"])
                except ValueError:
                    continue

                station = FuelStation(
                    opis_id=int(row["OPIS Truckstop ID"]),
                    name=row["Truckstop Name"].strip(),
                    address=row["Address"].strip(),
                    city=row["City"].strip(),
                    state=row["State"].strip(),
                    rack_id=int(row["Rack ID"]),
                    retail_price=price,
                )
                stations_to_create.append(station)

        self.stdout.write(f"Found {len(stations_to_create)} unique stations")

        self.stdout.write("Importing stations to database...")
        FuelStation.objects.bulk_create(stations_to_create, batch_size=batch_size)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported {len(stations_to_create)} fuel stations")
        )

        self.stdout.write("\nTo add coordinates, run: python manage.py geocode_stations --use-state-centroids")
