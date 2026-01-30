import requests
from typing import Tuple, List, Dict, Any, Optional


class RoutingService:
    NOMINATIM_URL = "https://nominatim.openstreetmap.org"
    OSRM_URL = "https://router.project-osrm.org"

    def __init__(self):
        self.headers = {"User-Agent": "FuelRouteOptimizer/1.0"}

    def geocode(self, location: str) -> Optional[Tuple[float, float]]:
        url = f"{self.NOMINATIM_URL}/search"
        params = {
            "q": f"{location}, USA",
            "format": "json",
            "limit": 1,
            "countrycodes": "us",
        }

        response = requests.get(url, params=params, headers=self.headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        if not data:
            return None

        return (float(data[0]["lon"]), float(data[0]["lat"]))

    def get_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
    ) -> Dict[str, Any]:
        coords_str = f"{start[0]},{start[1]};{end[0]},{end[1]}"

        url = f"{self.OSRM_URL}/route/v1/driving/{coords_str}"
        params = {
            "overview": "full",
            "geometries": "geojson",
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if data["code"] != "Ok":
            raise ValueError(f"OSRM error: {data.get('message', 'Unknown error')}")

        route = data["routes"][0]
        geometry = route["geometry"]

        distance_meters = route["distance"]
        duration_seconds = route["duration"]

        distance_miles = distance_meters / 1609.344

        return {
            "geometry": geometry["coordinates"],
            "distance_miles": round(distance_miles, 2),
            "duration_minutes": round(duration_seconds / 60, 1),
        }

    def simplify_points(
        self, points: List[Tuple[float, float]], max_points: int = 200
    ) -> List[Tuple[float, float]]:
        if len(points) <= max_points:
            return points

        step = len(points) / max_points
        simplified = []
        for i in range(max_points):
            idx = int(i * step)
            simplified.append(points[idx])

        if simplified[-1] != points[-1]:
            simplified.append(points[-1])

        return simplified

    def get_route_points(
        self, start: Tuple[float, float], end: Tuple[float, float]
    ) -> Tuple[List[Tuple[float, float]], float, float, List]:
        route_data = self.get_route(start, end)
        points = [(coord[0], coord[1]) for coord in route_data["geometry"]]

        return (
            points,
            route_data["distance_miles"],
            route_data["duration_minutes"],
            route_data["geometry"],
        )
