import os, sys, requests
from django.conf import settings
from django.http import JsonResponse
from django.urls import path
from django.core.management import execute_from_command_line
from jaeger_client import Config
from django_opentracing.middleware import OpenTracingMiddleware
from django_opentracing import DjangoTracer
import json
from datetime import datetime, date, timedelta
from dateutil import parser
import redis

# --- Configuration ---
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
SUNRISE_SUNSET_API_URL = "https://api.sunrisesunset.io/json"

# --- Environment Variables & Constants ---
# Use an environment variable for the Redis server address, default to localhost:6379
REDIS_SERVER = os.environ.get("REDIS_SERVER", "localhost:6379")
try:
    REDIS_HOST, REDIS_PORT = REDIS_SERVER.split(":")
except ValueError:
    print(f"ERROR: Invalid REDIS_SERVER format: {REDIS_SERVER}. Expected host:port.")
    REDIS_HOST, REDIS_PORT = "localhost", "6379" # Fallback
    
REDIS_KEY_PREFIX = "sunspot:data"

# TTLs in seconds
# Cache future/past dates for a long time (won't change)
LONG_TTL = 60 * 60 * 24 # 24 hours 
# Cache today/relative dates for a short time (to get fresh data tomorrow)
SHORT_TTL = 60 * 60 # 1 hour 

# --- Minimal Django setup ---
settings.configure(
    DEBUG=True,
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=["*"],
    MIDDLEWARE=['django_opentracing.middleware.OpenTracingMiddleware'],
)

# --- Service Initialization ---
def initialize_tracer():
    """Initializes the Jaeger tracer."""
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

def initialize_redis_client():
    """Initializes and pings the Redis client."""
    try:
        r = redis.Redis(host=REDIS_HOST, port=int(REDIS_PORT), decode_responses=True)
        r.ping()
        print(f"✅ Connected to Redis at {REDIS_SERVER}")
        return r
    except Exception as e:
        print(f"❌ Could not connect to Redis at {REDIS_SERVER}: {e}")
        return None

tracer = initialize_tracer()
django_tracer = DjangoTracer(tracer)
redis_client = initialize_redis_client() 

# --- Utility Functions ---
def resolve_date_param(date_param):
    """Resolves relative date strings ('today', 'yesterday', 'tomorrow') or a date string to a YYYY-MM-DD string."""
    today = date.today()
    if not date_param or date_param.lower() == 'today':
        return today.strftime('%Y-%m-%d')
    elif date_param.lower() == 'yesterday':
        return (today - timedelta(days=1)).strftime('%Y-%m-%d')
    elif date_param.lower() == 'tomorrow':
        return (today + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        # Check if the date_param is a valid date string
        try:
            # We only care about the date part for caching key, not time
            return parser.parse(date_param).strftime('%Y-%m-%d')
        except ValueError:
            return None # Invalid date format

# --- Core logic (Modified to include caching and logging) ---
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

def get_sunspot(lat, lon, date_param):
    """
    Fetches sunrise and sunset data, using Redis cache if available.
    Date parameter should be the raw input (e.g., 'today', '2025-10-05').
    """
    resolved_date_str = resolve_date_param(date_param)
    if not resolved_date_str:
        return None, None # Invalid date

    # Generate a unique cache key: sunspot:data:{latitude}:{longitude}:{YYYY-MM-DD}
    cache_key = f"{REDIS_KEY_PREFIX}:{lat}:{lon}:{resolved_date_str}"
    
    # Determine TTL
    is_today = resolved_date_str == date.today().strftime('%Y-%m-%d')
    ttl = SHORT_TTL if is_today else LONG_TTL
    
    sun_data = None
    
    # --- Caching Logic with Diagnostic Log ---
    if redis_client:
        with tracer.start_span("redis-get"):
            cached_data = redis_client.get(cache_key)
            
        if cached_data:
            # Cache HIT
            print(f"🎯 Cache HIT for key: {cache_key}")
            try:
                sun_data = json.loads(cached_data)
            except json.JSONDecodeError:
                print("⚠️ Error decoding cached data, fetching from API.")
                sun_data = None 
        else:
            # Cache MISS
            print(f"🔍 Cache MISS, fetching from API for key: {cache_key}")
    else:
        # Diagnostic Log
        print("🛑 WARNING: Redis client is not available (is None). Skipping caching.") 
    # --- End Caching Logic ---
        
    if sun_data is None:
        # Fetch from external API (only if cache missed or client is unavailable)
        try:
            with tracer.start_span("sunrisesunset-api-call"):
                # Construct parameters dictionary
                params = {"lat": lat, "lng": lon}
                # Use the raw date param so the API handles relative dates if necessary
                if date_param:
                    params["date"] = date_param 

                r = requests.get(SUNRISE_SUNSET_API_URL, params=params)
                r.raise_for_status()
                data = r.json()
                if data.get("status") == "OK":
                    sun_data = data["results"]
                
            if sun_data and redis_client:
                # Cache the fresh data
                with tracer.start_span("redis-set"):
                    # Store sun_data as a JSON string
                    redis_client.set(cache_key, json.dumps(sun_data), ex=ttl) 
                    print(f"💾 Cache SET for key: {cache_key} with TTL: {ttl}s")

        except Exception as e:
            print(f"❌ Error fetching sunspot data from API: {e}")
            pass

    return sun_data, resolved_date_str

# --- View (Modified to handle date resolution) ---
def sunspot_view(request):
    """
    Main view to handle sunspot queries by city or coordinates, with optional date.
    Includes city name in the response and uses caching.
    """
    city_name = None
    with tracer.start_span("sunspot_view"):
        city = request.GET.get("city")
        lat = request.GET.get("lat")
        lon = request.GET.get("lon")
        date_param = request.GET.get("date") # Raw date parameter

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

        # Retrieve sun data using the determined coordinates and optional date
        sun_data, resolved_date_str = get_sunspot(lat, lon, date_param)

        if sun_data:
            # Ensure city_name is not None
            if not city_name:
                city_name = f"Location {lat}, {lon}"

            return JsonResponse({
                "city": city_name,
                "latitude": lat,
                "longitude": lon,
                # Include the resolved date in the response for clarity
                "date_requested": resolved_date_str, 
                "sun_data": sun_data
            })
        else:
            return JsonResponse({"error": "Could not retrieve sunspot data or invalid date parameter"}, status=503)

# --- URL pattern ---
urlpatterns = [
    path("api/sunspot", sunspot_view),
]

# --- Run server ---
if __name__ == "__main__":
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])