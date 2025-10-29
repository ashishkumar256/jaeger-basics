import os, sys, requests
from django.conf import settings
from django.http import JsonResponse
from django.urls import path
from django.core.management import execute_from_command_line
from jaeger_client import Config
from django_opentracing.middleware import OpenTracingMiddleware
from django_opentracing import DjangoTracer

# --- Configuration ---
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
SUNRISE_SUNSET_API_URL = "https://api.sunrisesunset.io/json"

# --- Minimal Django setup ---
settings.configure(
    DEBUG=True,
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=["*"],
    MIDDLEWARE=['django_opentracing.middleware.OpenTracingMiddleware'],
)

# --- Jaeger tracer setup ---
def initialize_tracer():
    config = Config(
        config={
            'sampler': {'type': 'const', 'param': 1},
            'logging': True,
            'local_agent': {
                'reporting_host': 'jaeger-agent.tracing.svc',
                'reporting_port': 6831,
            },
        },
        service_name='sunspot-django-backend',
        validate=True,
    )
    return config.initialize_tracer()

tracer = initialize_tracer()
django_tracer = DjangoTracer(tracer)

# --- Core logic ---
def get_coordinates_from_city(city):
    """Translates a city name into latitude and longitude using Nominatim (OpenStreetMap)."""
    try:
        r = requests.get(NOMINATIM_SEARCH_URL, params={
            "city": city, "format": "json", "limit": 1
        }, headers={"User-Agent": "SunspotMinimal/1.0"})
        r.raise_for_status()
        data = r.json()
        if data and data[0].get("lat") and data[0].get("lon"):
            return data[0]["lat"], data[0]["lon"]
    except:
        pass
    return None, None

def get_city_from_coordinates(lat, lon):
    """Performs reverse geocoding to find a city name from coordinates."""
    try:
        r = requests.get(NOMINATIM_REVERSE_URL, params={
            "lat": lat, "lon": lon, "format": "json"
        }, headers={"User-Agent": "SunspotMinimal/1.0"})
        r.raise_for_status()
        data = r.json()
        
        # Attempt to extract common place names (city, town, village)
        address = data.get("address", {})
        return address.get("city") or address.get("town") or address.get("village") or address.get("hamlet") or data.get("display_name", f"Location {lat}, {lon}")
    except:
        pass
    # Fallback to coordinates if reverse lookup fails
    return f"Location {lat}, {lon}"

def get_sunspot(lat, lon):
    """Fetches sunrise and sunset data from sunrisesunset.io API."""
    try:
        r = requests.get(SUNRISE_SUNSET_API_URL, params={"lat": lat, "lng": lon})
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK":
            return data["results"]
    except:
        pass
    return None

# --- View ---
def sunspot_view(request):
    """
    Main view to handle sunspot queries by city or coordinates.
    Includes city name in the response.
    """
    city_name = None
    with tracer.start_span("sunspot_view"):
        city = request.GET.get("city")
        lat = request.GET.get("lat")
        lon = request.GET.get("lon")

        if city:
            # Case 1: Query by City Name
            city_name = city.strip()
            lat, lon = get_coordinates_from_city(city_name)
            if not lat or not lon:
                return JsonResponse({"error": f"Could not find coordinates for city: {city_name}"}, status=404)
        elif lat and lon:
            # Case 2: Query by Coordinates (Reverse Lookup Required)
            try:
                lat = str(float(lat))
                lon = str(float(lon))
                # Perform reverse lookup to get city name for the response
                city_name = get_city_from_coordinates(lat, lon)
            except ValueError:
                return JsonResponse({"error": "Invalid lat/lon format"}, status=400)
        else:
            # Case 3: Missing Parameters
            return JsonResponse({"error": "Missing city or lat/lon"}, status=400)

        # Retrieve sun data using the determined coordinates
        sun_data = get_sunspot(lat, lon)
        
        if sun_data:
            # Ensure city_name is not None (should be handled by logic above, but safety check)
            if not city_name:
                city_name = f"Location {lat}, {lon}" 
                
            return JsonResponse({
                "city": city_name,
                "latitude": lat,
                "longitude": lon,
                "sun_data": sun_data
            })
        else:
            return JsonResponse({"error": "Could not retrieve sunspot data"}, status=503)

# --- URL pattern ---
urlpatterns = [
    path("api/sunspot", sunspot_view),
]

# --- Run server ---
if __name__ == "__main__":
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
