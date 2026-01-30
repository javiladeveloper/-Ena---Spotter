from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .serializers import RouteRequestSerializer
from .services import RoutingService, FuelOptimizerService


def map_view(request):
    return render(request, 'fuel_optimizer/map.html')


class CalculateRouteView(APIView):
    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start = serializer.validated_data["start"]
        finish = serializer.validated_data["finish"]
        start_fuel_level = serializer.validated_data.get("start_fuel_level", 1.0)

        try:
            routing_service = RoutingService()
            fuel_optimizer = FuelOptimizerService()

            start_coords = routing_service.geocode(start)
            if not start_coords:
                return Response(
                    {"error": f"Could not find location: {start}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            end_coords = routing_service.geocode(finish)
            if not end_coords:
                return Response(
                    {"error": f"Could not find location: {finish}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            route_points, total_distance, duration, _ = routing_service.get_route_points(
                start_coords, end_coords
            )

            simplified_points = routing_service.simplify_points(route_points, max_points=300)

            fuel_stops = fuel_optimizer.find_optimal_stops(
                simplified_points,
                total_distance,
                start_fuel_level=start_fuel_level,
            )

            summary = fuel_optimizer.calculate_trip_summary(total_distance, fuel_stops)

            response_points = routing_service.simplify_points(route_points, max_points=100)

            response_data = {
                "start_location": {
                    "address": start,
                    "longitude": start_coords[0],
                    "latitude": start_coords[1],
                },
                "end_location": {
                    "address": finish,
                    "longitude": end_coords[0],
                    "latitude": end_coords[1],
                },
                "route": {
                    "distance_miles": total_distance,
                    "duration_minutes": duration,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[p[0], p[1]] for p in response_points],
                    },
                },
                "fuel_stops": fuel_stops,
                "summary": summary,
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class HealthCheckView(APIView):
    def get(self, request):
        from .models import FuelStation

        station_count = FuelStation.objects.count()
        geocoded_count = FuelStation.objects.exclude(latitude__isnull=True).count()

        return Response(
            {
                "status": "healthy",
                "fuel_stations_loaded": station_count,
                "stations_with_coordinates": geocoded_count,
            }
        )
