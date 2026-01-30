import time
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from fuel_optimizer.models import FuelStation


STATE_CENTROIDS = {
    "AL": (32.806671, -86.791130), "AK": (61.370716, -152.404419),
    "AZ": (33.729759, -111.431221), "AR": (34.969704, -92.373123),
    "CA": (36.116203, -119.681564), "CO": (39.059811, -105.311104),
    "CT": (41.597782, -72.755371), "DE": (39.318523, -75.507141),
    "FL": (27.766279, -81.686783), "GA": (33.040619, -83.643074),
    "HI": (21.094318, -157.498337), "ID": (44.240459, -114.478828),
    "IL": (40.349457, -88.986137), "IN": (39.849426, -86.258278),
    "IA": (42.011539, -93.210526), "KS": (38.526600, -96.726486),
    "KY": (37.668140, -84.670067), "LA": (31.169546, -91.867805),
    "ME": (44.693947, -69.381927), "MD": (39.063946, -76.802101),
    "MA": (42.230171, -71.530106), "MI": (43.326618, -84.536095),
    "MN": (45.694454, -93.900192), "MS": (32.741646, -89.678696),
    "MO": (38.456085, -92.288368), "MT": (46.921925, -110.454353),
    "NE": (41.125370, -98.268082), "NV": (38.313515, -117.055374),
    "NH": (43.452492, -71.563896), "NJ": (40.298904, -74.521011),
    "NM": (34.840515, -106.248482), "NY": (42.165726, -74.948051),
    "NC": (35.630066, -79.806419), "ND": (47.528912, -99.784012),
    "OH": (40.388783, -82.764915), "OK": (35.565342, -96.928917),
    "OR": (44.572021, -122.070938), "PA": (40.590752, -77.209755),
    "RI": (41.680893, -71.511780), "SC": (33.856892, -80.945007),
    "SD": (44.299782, -99.438828), "TN": (35.747845, -86.692345),
    "TX": (31.054487, -97.563461), "UT": (40.150032, -111.862434),
    "VT": (44.045876, -72.710686), "VA": (37.769337, -78.169968),
    "WA": (47.400902, -121.490494), "WV": (38.491226, -80.954453),
    "WI": (44.268543, -89.616508), "WY": (42.755966, -107.302490),
    "DC": (38.897438, -77.026817),
}


class Command(BaseCommand):
    help = "Geocode fuel stations"

    def add_arguments(self, parser):
        parser.add_argument("--use-state-centroids", action="store_true")
        parser.add_argument("--limit", type=int, default=0)

    def geocode_with_ors(self, city: str, state: str) -> tuple:
        api_key = getattr(settings, 'OPENROUTESERVICE_API_KEY', None)
        if not api_key:
            return None, None

        url = "https://api.openrouteservice.org/geocode/search"
        params = {
            "api_key": api_key,
            "text": f"{city}, {state}, USA",
            "boundary.country": "US",
            "size": 1,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("features"):
                coords = data["features"][0]["geometry"]["coordinates"]
                return coords[1], coords[0]
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Geocoding error for {city}, {state}: {e}"))

        return None, None

    def handle(self, *args, **options):
        use_centroids = options["use_state_centroids"]
        limit = options["limit"]

        stations = FuelStation.objects.filter(latitude__isnull=True)
        total = stations.count()

        if limit > 0:
            stations = stations[:limit]
            total = min(total, limit)

        self.stdout.write(f"Geocoding {total} stations...")

        if use_centroids:
            self.stdout.write("Using state centroids (fast mode)...")
            from django.db.models import Count

            state_counts = (
                FuelStation.objects.filter(latitude__isnull=True)
                .values("state")
                .annotate(count=Count("id"))
            )

            for state_info in state_counts:
                state = state_info["state"]
                if state in STATE_CENTROIDS:
                    lat, lon = STATE_CENTROIDS[state]
                    updated = FuelStation.objects.filter(
                        state=state, latitude__isnull=True
                    ).update(latitude=lat, longitude=lon)
                    self.stdout.write(f"Updated {updated} stations in {state}")
                else:
                    self.stdout.write(self.style.WARNING(f"No centroid for state: {state}"))
        else:
            city_cache = {}
            geocoded = 0
            failed = 0

            for i, station in enumerate(stations.iterator()):
                city_key = (station.city.lower(), station.state)

                if city_key not in city_cache:
                    lat, lon = self.geocode_with_ors(station.city, station.state)
                    city_cache[city_key] = (lat, lon)
                    time.sleep(0.5)

                lat, lon = city_cache[city_key]

                if lat and lon:
                    station.latitude = lat
                    station.longitude = lon
                    station.save(update_fields=["latitude", "longitude"])
                    geocoded += 1
                else:
                    if station.state in STATE_CENTROIDS:
                        lat, lon = STATE_CENTROIDS[station.state]
                        station.latitude = lat
                        station.longitude = lon
                        station.save(update_fields=["latitude", "longitude"])
                        geocoded += 1
                    else:
                        failed += 1

                if (i + 1) % 50 == 0:
                    self.stdout.write(f"Progress: {i + 1}/{total} (geocoded: {geocoded}, failed: {failed})")

            self.stdout.write(self.style.SUCCESS(f"Geocoding complete: {geocoded} successful, {failed} failed"))

        with_coords = FuelStation.objects.exclude(latitude__isnull=True).count()
        without_coords = FuelStation.objects.filter(latitude__isnull=True).count()

        self.stdout.write(f"\nFinal stats:")
        self.stdout.write(f"  Stations with coordinates: {with_coords}")
        self.stdout.write(f"  Stations without coordinates: {without_coords}")
