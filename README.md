# Fuel Route Optimizer API

Django REST API that calculates optimal fuel stops for road trips across the USA. Given a start and finish location, returns the route with cost-effective fuel stop recommendations.

## Features

- Calculate optimal fuel stops for any route in the USA
- 8,000+ fuel stations with real prices
- Vehicle: 500 miles max range, 10 MPG consumption
- Returns route geometry, fuel stops, and total cost
- Fast responses (2-4 seconds)

## Tech Stack

- **Django 5** + Django REST Framework
- **SQLite** for fuel station data
- **Nominatim** (OpenStreetMap) - Geocoding, free, no API key
- **OSRM** (OpenStreetMap) - Routing, free, no API key

## Quick Start

```bash
cd fuel_route_api

# Create virtual environment
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Import fuel data from CSV
python manage.py import_fuel_data ../fuel-prices-for-be-assessment.csv

# Add coordinates to stations
python manage.py geocode_stations --use-state-centroids

# Run server
python manage.py runserver
```

## API Endpoints

### Health Check

```
GET /api/health/
```

```json
{
    "status": "healthy",
    "fuel_stations_loaded": 8125,
    "stations_with_coordinates": 8125
}
```

### Calculate Route

```
POST /api/route/
Content-Type: application/json

{
    "start": "Houston, TX",
    "finish": "Miami, FL"
}
```

**Response:**
```json
{
    "start_location": {
        "address": "Houston, TX",
        "longitude": -95.3698,
        "latitude": 29.7604
    },
    "end_location": {
        "address": "Miami, FL",
        "longitude": -80.1918,
        "latitude": 25.7617
    },
    "route": {
        "distance_miles": 1186.5,
        "duration_minutes": 1020.3,
        "geometry": { "type": "LineString", "coordinates": [...] }
    },
    "fuel_stops": [
        {
            "station": {
                "name": "AAA HOSPITALITY",
                "city": "TILLATOBA",
                "state": "MS",
                "price_per_gallon": 2.784
            },
            "distance_from_start": 450.2,
            "gallons_to_add": 45.0,
            "cost": 125.28
        }
    ],
    "summary": {
        "total_distance_miles": 1186.5,
        "total_fuel_cost": 253.42,
        "number_of_stops": 2,
        "vehicle_mpg": 10,
        "vehicle_max_range": 500
    }
}
```

## Project Structure

```
fuel_route_api/
├── fuel_route_api/          # Django project config
│   ├── settings.py          # DB, vehicle settings
│   └── urls.py              # API routes
├── fuel_optimizer/          # Main app
│   ├── models.py            # FuelStation model
│   ├── views.py             # API endpoints
│   ├── serializers.py       # Request validation
│   └── services/
│       ├── routing.py       # Nominatim + OSRM integration
│       └── fuel_optimizer.py # Optimization algorithm
└── manage.py
```

## How It Works

1. **Geocoding**: Converts city names to coordinates (Nominatim)
2. **Routing**: Gets driving route between points (OSRM)
3. **Optimization**: Divides route into 500-mile segments, finds cheapest station in each
4. **Response**: Returns route with optimal stops and total cost

**Only 3 external API calls** per request:
- 2 for geocoding (start + finish)
- 1 for routing

All fuel station lookups are local database queries.

## Configuration

Vehicle settings in `settings.py`:

| Setting | Default |
|---------|---------|
| `VEHICLE_MAX_RANGE_MILES` | 500 |
| `VEHICLE_MPG` | 10 |
