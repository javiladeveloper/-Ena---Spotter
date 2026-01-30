"""
Fuel optimization service for finding optimal fuel stops along a route.
"""
import math
from typing import List, Dict, Any, Tuple, Optional
from django.conf import settings
from django.db.models import QuerySet

from ..models import FuelStation


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great circle distance between two points on Earth.

    Args:
        lat1, lon1: Coordinates of first point
        lat2, lon2: Coordinates of second point

    Returns:
        Distance in miles
    """
    R = 3959  # Earth's radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def point_to_segment_distance(
    point: Tuple[float, float],
    segment_start: Tuple[float, float],
    segment_end: Tuple[float, float],
) -> float:
    """
    Calculate the perpendicular distance from a point to a line segment.

    Uses a simplified approach for short segments (assumes flat Earth locally).
    """
    px, py = point[1], point[0]  # lat, lon
    x1, y1 = segment_start[1], segment_start[0]
    x2, y2 = segment_end[1], segment_end[0]

    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return haversine_distance(py, px, y1, x1)

    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))

    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy

    return haversine_distance(py, px, nearest_y, nearest_x)


class FuelOptimizerService:
    """Service for finding optimal fuel stops along a route."""

    def __init__(
        self,
        max_range: float = None,
        mpg: float = None,
        search_radius: float = 150,  # Increased to handle approximate coordinates
    ):
        """
        Initialize the fuel optimizer.

        Args:
            max_range: Maximum vehicle range in miles (default from settings)
            mpg: Vehicle fuel efficiency in miles per gallon (default from settings)
            search_radius: How far off route to search for stations (miles)
        """
        self.max_range = max_range or settings.VEHICLE_MAX_RANGE_MILES
        self.mpg = mpg or settings.VEHICLE_MPG
        self.search_radius = search_radius

    def find_stations_near_route(
        self,
        route_points: List[Tuple[float, float]],
        max_distance_from_route: float = None,
    ) -> List:
        """
        Find all fuel stations near the route.

        Args:
            route_points: List of (longitude, latitude) points along the route
            max_distance_from_route: Maximum distance from route in miles

        Returns:
            List of FuelStation objects near the route, ordered by price
        """
        if max_distance_from_route is None:
            max_distance_from_route = self.search_radius

        # Get bounding box of the route with generous padding
        # Using larger padding to account for stations with approximate coordinates
        lons = [p[0] for p in route_points]
        lats = [p[1] for p in route_points]

        min_lon = min(lons) - 2.0  # ~120 miles padding
        max_lon = max(lons) + 2.0
        min_lat = min(lats) - 2.0
        max_lat = max(lats) + 2.0

        # Get stations within bounding box, ordered by price
        stations = FuelStation.objects.filter(
            longitude__gte=min_lon,
            longitude__lte=max_lon,
            latitude__gte=min_lat,
            latitude__lte=max_lat,
            latitude__isnull=False,
            longitude__isnull=False,
        ).order_by('retail_price').only(
            'id', 'name', 'address', 'city', 'state',
            'retail_price', 'latitude', 'longitude'
        )[:1000]  # Limit to 1000 cheapest stations for better coverage

        return list(stations)

    def calculate_distance_along_route(
        self,
        route_points: List[Tuple[float, float]],
        station_lat: float,
        station_lon: float,
    ) -> Tuple[float, float]:
        """
        Calculate distance along route to the nearest point to a station.

        Returns:
            Tuple of (distance along route in miles, distance from route in miles)
        """
        cumulative_distance = 0.0
        min_distance_from_route = float("inf")
        distance_at_nearest = 0.0

        for i in range(len(route_points) - 1):
            p1 = route_points[i]
            p2 = route_points[i + 1]

            # Distance of this segment
            segment_dist = haversine_distance(p1[1], p1[0], p2[1], p2[0])

            # Distance from station to this segment
            dist_from_route = point_to_segment_distance(
                (station_lon, station_lat), p1, p2
            )

            if dist_from_route < min_distance_from_route:
                min_distance_from_route = dist_from_route
                # Estimate where along the segment the nearest point is
                dist_to_p1 = haversine_distance(station_lat, station_lon, p1[1], p1[0])
                dist_to_p2 = haversine_distance(station_lat, station_lon, p2[1], p2[0])

                if segment_dist > 0:
                    # Use projection to estimate position along segment
                    t = max(
                        0,
                        min(
                            1,
                            (dist_to_p1**2 - dist_to_p2**2 + segment_dist**2)
                            / (2 * segment_dist**2)
                            * segment_dist,
                        ),
                    )
                else:
                    t = 0

                distance_at_nearest = cumulative_distance + t

            cumulative_distance += segment_dist

        return distance_at_nearest, min_distance_from_route

    def find_optimal_stops(
        self,
        route_points: List[Tuple[float, float]],
        total_distance: float,
        start_fuel_level: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Find optimal fuel stops along a route.

        Strategy: Divide route into segments based on vehicle range and find
        the cheapest station in each segment where refueling is needed.

        Args:
            route_points: List of (longitude, latitude) points along the route
            total_distance: Total route distance in miles
            start_fuel_level: Starting fuel level as fraction (1.0 = full tank)

        Returns:
            List of optimal fuel stops with station info and fuel amounts
        """
        # Safety margin - don't let tank go below 10%
        safety_margin = 0.1
        effective_range = self.max_range * (1 - safety_margin)
        tank_capacity_gallons = self.max_range / self.mpg

        # Get all stations in the route corridor
        all_stations = self.find_stations_near_route(route_points)

        if not all_stations:
            return []

        # Calculate approximate position for each station along the route
        station_data = []
        for station in all_stations:
            dist_along, dist_from = self.calculate_distance_along_route(
                route_points, station.latitude, station.longitude
            )
            station_data.append({
                "station": station,
                "distance_along_route": dist_along,
                "distance_from_route": dist_from,
                "price": float(station.retail_price),
            })

        # Sort by distance along route
        station_data.sort(key=lambda x: x["distance_along_route"])

        # Find optimal stops using segment-based approach
        optimal_stops = []
        current_position = 0.0
        current_range = self.max_range * start_fuel_level

        while current_position < total_distance:
            remaining_distance = total_distance - current_position

            # If we can reach the destination, we're done
            if current_range >= remaining_distance:
                break

            # Define the segment where we need to stop (before running out of fuel)
            segment_start = current_position
            segment_end = current_position + effective_range

            # Find all stations in this segment
            segment_stations = [
                s for s in station_data
                if segment_start < s["distance_along_route"] <= segment_end
            ]

            if not segment_stations:
                # No stations in segment - try to find any station ahead
                ahead_stations = [
                    s for s in station_data
                    if s["distance_along_route"] > current_position
                ]
                if ahead_stations:
                    # Take the first station ahead (closest)
                    segment_stations = [ahead_stations[0]]
                else:
                    # No more stations - can't complete the route
                    break

            # Pick the cheapest station in this segment
            # Prefer stations further along to minimize stops
            best_station = min(
                segment_stations,
                key=lambda s: (s["price"], -s["distance_along_route"])
            )

            # Calculate fuel to add
            distance_to_station = best_station["distance_along_route"] - current_position
            fuel_used = distance_to_station / self.mpg
            remaining_fuel = (current_range / self.mpg) - fuel_used

            # Fill up the tank
            gallons_to_add = tank_capacity_gallons - max(0, remaining_fuel)
            gallons_to_add = max(0, min(gallons_to_add, tank_capacity_gallons))

            cost = gallons_to_add * best_station["price"]

            optimal_stops.append({
                "station": {
                    "id": best_station["station"].id,
                    "name": best_station["station"].name,
                    "address": best_station["station"].address,
                    "city": best_station["station"].city,
                    "state": best_station["station"].state,
                    "price_per_gallon": best_station["price"],
                    "latitude": best_station["station"].latitude,
                    "longitude": best_station["station"].longitude,
                },
                "distance_from_start": round(best_station["distance_along_route"], 1),
                "distance_from_route": round(best_station["distance_from_route"], 1),
                "gallons_to_add": round(gallons_to_add, 2),
                "cost": round(cost, 2),
            })

            # Update state - move to station position with full tank
            current_position = best_station["distance_along_route"]
            current_range = self.max_range

        return optimal_stops

    def calculate_trip_summary(
        self,
        total_distance: float,
        stops: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculate summary statistics for the trip.

        Args:
            total_distance: Total route distance in miles
            stops: List of fuel stops

        Returns:
            Dictionary with trip summary
        """
        total_gallons = sum(stop["gallons_to_add"] for stop in stops)
        total_fuel_cost = sum(stop["cost"] for stop in stops)

        # Calculate average price paid
        avg_price = total_fuel_cost / total_gallons if total_gallons > 0 else 0

        return {
            "total_distance_miles": round(total_distance, 1),
            "total_gallons_needed": round(total_distance / self.mpg, 2),
            "total_gallons_purchased": round(total_gallons, 2),
            "total_fuel_cost": round(total_fuel_cost, 2),
            "average_price_per_gallon": round(avg_price, 3),
            "number_of_stops": len(stops),
            "vehicle_mpg": self.mpg,
            "vehicle_max_range": self.max_range,
        }
