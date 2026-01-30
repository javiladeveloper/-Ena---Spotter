"""
Unit tests for the Fuel Route Optimizer API.
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status

from .models import FuelStation
from .services import RoutingService, FuelOptimizerService


class FuelStationModelTest(TestCase):
    """Tests for the FuelStation model."""

    def setUp(self):
        self.station = FuelStation.objects.create(
            opis_id=12345,
            name="TEST STATION",
            address="123 Main St",
            city="Houston",
            state="TX",
            rack_id=1,
            retail_price=Decimal("2.999"),
            latitude=29.7604,
            longitude=-95.3698,
        )

    def test_station_creation(self):
        """Test that a fuel station can be created."""
        self.assertEqual(self.station.name, "TEST STATION")
        self.assertEqual(self.station.state, "TX")
        self.assertEqual(float(self.station.retail_price), 2.999)

    def test_station_str(self):
        """Test the string representation."""
        expected = "TEST STATION - Houston, TX ($2.999/gal)"
        self.assertEqual(str(self.station), expected)

    def test_station_coordinates(self):
        """Test that coordinates are stored correctly."""
        self.assertAlmostEqual(self.station.latitude, 29.7604, places=4)
        self.assertAlmostEqual(self.station.longitude, -95.3698, places=4)


class FuelOptimizerServiceTest(TestCase):
    """Tests for the FuelOptimizerService."""

    def setUp(self):
        # Create test stations along a route
        self.stations = [
            FuelStation.objects.create(
                opis_id=1,
                name="CHEAP STATION",
                address="100 Highway",
                city="Austin",
                state="TX",
                rack_id=1,
                retail_price=Decimal("2.50"),
                latitude=30.2672,
                longitude=-97.7431,
            ),
            FuelStation.objects.create(
                opis_id=2,
                name="EXPENSIVE STATION",
                address="200 Highway",
                city="San Antonio",
                state="TX",
                rack_id=1,
                retail_price=Decimal("3.50"),
                latitude=29.4241,
                longitude=-98.4936,
            ),
        ]
        self.optimizer = FuelOptimizerService(max_range=500, mpg=10)

    def test_optimizer_initialization(self):
        """Test optimizer initializes with correct values."""
        self.assertEqual(self.optimizer.max_range, 500)
        self.assertEqual(self.optimizer.mpg, 10)

    def test_find_stations_near_route(self):
        """Test finding stations near a route."""
        # Route points from Houston to Dallas (roughly)
        route_points = [
            (-95.3698, 29.7604),  # Houston
            (-97.7431, 30.2672),  # Austin
            (-96.7970, 32.7767),  # Dallas
        ]

        stations = self.optimizer.find_stations_near_route(route_points)
        self.assertGreater(len(stations), 0)

    def test_calculate_trip_summary(self):
        """Test trip summary calculation."""
        stops = [
            {"gallons_to_add": 40, "cost": 100.0},
            {"gallons_to_add": 35, "cost": 87.5},
        ]

        summary = self.optimizer.calculate_trip_summary(
            total_distance=750.0,
            stops=stops
        )

        self.assertEqual(summary["total_distance_miles"], 750.0)
        self.assertEqual(summary["total_gallons_purchased"], 75.0)
        self.assertEqual(summary["total_fuel_cost"], 187.5)
        self.assertEqual(summary["number_of_stops"], 2)


class RoutingServiceTest(TestCase):
    """Tests for the RoutingService."""

    def setUp(self):
        self.routing = RoutingService()

    @patch('fuel_optimizer.services.routing.requests.get')
    def test_geocode_success(self, mock_get):
        """Test successful geocoding."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"lat": "29.7604", "lon": "-95.3698"}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = self.routing.geocode("Houston, TX")

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], -95.3698, places=4)
        self.assertAlmostEqual(result[1], 29.7604, places=4)

    @patch('fuel_optimizer.services.routing.requests.get')
    def test_geocode_not_found(self, mock_get):
        """Test geocoding when location not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = self.routing.geocode("Nonexistent Place, XX")

        self.assertIsNone(result)

    @patch('fuel_optimizer.services.routing.requests.get')
    def test_get_route_success(self, mock_get):
        """Test successful route calculation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "Ok",
            "routes": [{
                "distance": 314159,  # meters
                "duration": 12000,   # seconds
                "geometry": {
                    "coordinates": [
                        [-95.3698, 29.7604],
                        [-97.7431, 30.2672],
                    ]
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = self.routing.get_route(
            (-95.3698, 29.7604),
            (-97.7431, 30.2672)
        )

        self.assertIn("distance_miles", result)
        self.assertIn("duration_minutes", result)
        self.assertIn("geometry", result)

    def test_simplify_points(self):
        """Test point simplification."""
        points = [(i, i) for i in range(100)]
        simplified = self.routing.simplify_points(points, max_points=10)

        self.assertLessEqual(len(simplified), 11)  # max + possible last point
        self.assertEqual(simplified[0], points[0])  # First point preserved


class HealthCheckAPITest(APITestCase):
    """Tests for the health check endpoint."""

    def test_health_check(self):
        """Test health check returns correct data."""
        response = self.client.get('/api/health/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')
        self.assertIn('fuel_stations_loaded', response.data)
        self.assertIn('stations_with_coordinates', response.data)


class RouteAPITest(APITestCase):
    """Tests for the route calculation endpoint."""

    def test_route_missing_start(self):
        """Test error when start is missing."""
        response = self.client.post('/api/route/', {
            'finish': 'Miami, FL'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_route_missing_finish(self):
        """Test error when finish is missing."""
        response = self.client.post('/api/route/', {
            'start': 'Houston, TX'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch.object(RoutingService, 'geocode')
    @patch.object(RoutingService, 'get_route_points')
    def test_route_location_not_found(self, mock_route, mock_geocode):
        """Test error when location cannot be geocoded."""
        mock_geocode.return_value = None

        response = self.client.post('/api/route/', {
            'start': 'Nonexistent, XX',
            'finish': 'Miami, FL'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    @patch.object(RoutingService, 'geocode')
    @patch.object(RoutingService, 'get_route_points')
    @patch.object(FuelOptimizerService, 'find_optimal_stops')
    def test_route_success(self, mock_stops, mock_route, mock_geocode):
        """Test successful route calculation."""
        # Mock geocoding
        mock_geocode.side_effect = [
            (-95.3698, 29.7604),  # Houston
            (-80.1918, 25.7617),  # Miami
        ]

        # Mock route
        mock_route.return_value = (
            [(-95.3698, 29.7604), (-80.1918, 25.7617)],
            1186.5,
            1020.3,
            [[-95.3698, 29.7604], [-80.1918, 25.7617]]
        )

        # Mock fuel stops
        mock_stops.return_value = []

        response = self.client.post('/api/route/', {
            'start': 'Houston, TX',
            'finish': 'Miami, FL'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('start_location', response.data)
        self.assertIn('end_location', response.data)
        self.assertIn('route', response.data)
        self.assertIn('summary', response.data)


class HaversineDistanceTest(TestCase):
    """Tests for the haversine distance calculation."""

    def test_haversine_same_point(self):
        """Test distance between same point is zero."""
        from .services.fuel_optimizer import haversine_distance

        distance = haversine_distance(29.7604, -95.3698, 29.7604, -95.3698)
        self.assertEqual(distance, 0)

    def test_haversine_known_distance(self):
        """Test distance between Houston and Austin (~165 miles)."""
        from .services.fuel_optimizer import haversine_distance

        # Houston to Austin
        distance = haversine_distance(
            29.7604, -95.3698,  # Houston
            30.2672, -97.7431   # Austin
        )

        # Should be approximately 165 miles (allowing some tolerance)
        self.assertGreater(distance, 140)
        self.assertLess(distance, 180)
