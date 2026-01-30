"""
URL configuration for fuel_route_api project.
"""
from django.contrib import admin
from django.urls import path, include
from fuel_optimizer.views import map_view

urlpatterns = [
    path('', map_view, name='map'),
    path('admin/', admin.site.urls),
    path('api/', include('fuel_optimizer.urls')),
]
