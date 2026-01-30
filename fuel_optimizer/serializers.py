from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField()
    finish = serializers.CharField()
    start_fuel_level = serializers.FloatField(
        default=1.0,
        min_value=0.0,
        max_value=1.0,
    )


class FuelStationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    price_per_gallon = serializers.FloatField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class FuelStopSerializer(serializers.Serializer):
    station = FuelStationSerializer()
    distance_from_start = serializers.FloatField()
    distance_from_route = serializers.FloatField()
    gallons_to_add = serializers.FloatField()
    cost = serializers.FloatField()


class TripSummarySerializer(serializers.Serializer):
    total_distance_miles = serializers.FloatField()
    total_gallons_needed = serializers.FloatField()
    total_gallons_purchased = serializers.FloatField()
    total_fuel_cost = serializers.FloatField()
    average_price_per_gallon = serializers.FloatField()
    number_of_stops = serializers.IntegerField()
    vehicle_mpg = serializers.FloatField()
    vehicle_max_range = serializers.FloatField()


class RouteResponseSerializer(serializers.Serializer):
    start_location = serializers.DictField()
    end_location = serializers.DictField()
    route = serializers.DictField()
    fuel_stops = FuelStopSerializer(many=True)
    summary = TripSummarySerializer()
