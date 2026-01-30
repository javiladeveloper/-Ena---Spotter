"""
Serializers for the fuel optimizer API.
"""
from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    """Serializer for route calculation requests."""

    start = serializers.CharField(
        help_text="Starting location (e.g., 'New York, NY' or 'Los Angeles, CA')"
    )
    finish = serializers.CharField(
        help_text="Destination location (e.g., 'Chicago, IL')"
    )
    start_fuel_level = serializers.FloatField(
        default=1.0,
        min_value=0.0,
        max_value=1.0,
        help_text="Starting fuel level as a fraction (0.0 to 1.0, default 1.0 = full tank)",
    )


class FuelStationSerializer(serializers.Serializer):
    """Serializer for fuel station data."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    price_per_gallon = serializers.FloatField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class FuelStopSerializer(serializers.Serializer):
    """Serializer for a recommended fuel stop."""

    station = FuelStationSerializer()
    distance_from_start = serializers.FloatField(
        help_text="Distance from start in miles"
    )
    distance_from_route = serializers.FloatField(
        help_text="Distance from the main route in miles"
    )
    gallons_to_add = serializers.FloatField(help_text="Recommended gallons to purchase")
    cost = serializers.FloatField(help_text="Estimated cost for fuel at this stop")


class TripSummarySerializer(serializers.Serializer):
    """Serializer for trip summary statistics."""

    total_distance_miles = serializers.FloatField()
    total_gallons_needed = serializers.FloatField()
    total_gallons_purchased = serializers.FloatField()
    total_fuel_cost = serializers.FloatField()
    average_price_per_gallon = serializers.FloatField()
    number_of_stops = serializers.IntegerField()
    vehicle_mpg = serializers.FloatField()
    vehicle_max_range = serializers.FloatField()


class RouteResponseSerializer(serializers.Serializer):
    """Serializer for the complete route response."""

    start_location = serializers.DictField(
        help_text="Starting point coordinates and address"
    )
    end_location = serializers.DictField(
        help_text="Destination coordinates and address"
    )
    route = serializers.DictField(help_text="Route geometry and metadata")
    fuel_stops = FuelStopSerializer(many=True)
    summary = TripSummarySerializer()
