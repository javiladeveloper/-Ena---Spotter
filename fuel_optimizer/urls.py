"""
URL configuration for the fuel optimizer API.
"""
from django.urls import path
from .views import CalculateRouteView, HealthCheckView

urlpatterns = [
    path("route/", CalculateRouteView.as_view(), name="calculate-route"),
    path("health/", HealthCheckView.as_view(), name="health-check"),
]
