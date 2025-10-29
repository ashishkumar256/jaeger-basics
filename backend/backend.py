import os, sys, requests, json, logging
from datetime import date, timedelta
from dateutil import parser
from django.conf import settings
from django.http import JsonResponse
from django.urls import path
from django.core.management import execute_from_command_line
from jaeger_client import Config
from django_opentracing.middleware import OpenTracingMiddleware
from django_opentracing import DjangoTracer
import redis

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("sunspot")

# --- Configuration ---
SUNRISE_SUNSET_API_URL = "https://api.sunrisesunset.io/json"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

REDIS_SERVER = os.environ.get("REDIS_SERVER", "localhost:6379")
REDIS_HOST, REDIS_PORT = REDIS_SERVER.split(":")
REDIS_KEY_PREFIX = "sunspot:data"
LONG_TTL = 7 * 60 * 60 * 24
SHORT_TTL = 60 * 60 * 24

# --- Minimal Django setup ---
settings.configure(
    DEBUG=True,
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=["*"],
    MIDDLEWARE=['django_opentracing.middleware.OpenTracingMiddleware'],
)

# --- Service Initialization ---
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

def initialize_redis_client():
    try:
        r = redis.Redis(host=REDIS_HOST, port=int(REDIS_PORT), decode_responses=True)
        r.ping()
        logger.info(f"Connected to Redis at {REDIS_SERVER}")
        return r
    except Exception as e:
        logger.warning(f"Could not connect to Redis at {REDIS_SERVER}: {e}")
        return None

tracer = initialize_tracer()
django_tracer = DjangoTracer(tracer)
redis_client = initialize_redis_client()

# --- Utility Functions ---
def resolve_date_param(date_param):
    today = date.today()
    if not date_param or date_param.lower() == 'today':
        return today.strftime('%Y-%m-%d')
    elif date_param.lower() == 'yesterday':
        return (today - timedelta(days=1)).strftime('%Y-%m-%d')
    elif date_param.lower() == 'tomorrow':
        return (today + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        try:
            return parser.parse(date_param).strftime('%Y-%m-%d')
        except ValueError:
            return None

def get_coordinates_from_city(city):
    try:
        r = requests.get(NOMINATIM_SEARCH_URL, params={
            "city": city, "format": "json", "limit": 1
        }, headers={"User-Agent": "SunspotMinimal/1.0"})
        r.raise_for_status()
        data = r.json()
        if data and data[0].get("lat") and data[0].get("lon"):
            return data[0]["lat"], data[0]["lon"]
    except Exception as e:
        logger.warning(f"Error fetching coordinates for city '{city}': {e}")
    return None, None

def get_city_from_coordinates(lat, lon):
    try:
        r = requests.get(NOMINATIM_REVERSE_URL, params={
            "lat": lat, "lon": lon, "format": "json"
        }, headers={"User-Agent": "SunspotMinimal/1.0"})
        r.raise_for_status()
        data = r.json()
        address = data.get("address", {})
        return address.get("city") or address.get("town") or address.get("village") or address.get("hamlet") or data.get("display_name", f"Location {lat}, {lon}")
    except Exception as e:
        logger.warning(f"Error reverse geocoding {lat}, {lon}: {e}")
    return f"Location {lat}, {lon}"

def get_sunspot(lat, lon, date_param):
    resolved_date_str = resolve_date_param(date_param)
    if not resolved_date_str:
        return None, None

    cache_key = f"{REDIS_KEY_PREFIX}:{lat}:{lon}:{resolved_date_str}"
    is_today = resolved_date_str == date.today().strftime('%Y-%m-%d')
    ttl = SHORT_TTL if is_today else LONG_TTL
    sun_data = None

    if redis_client:
        with tracer.start_span("redis-get"):
            cached_data = redis_client.get(cache_key)
        if cached_data:
            logger.info(f"Cache HIT for key: {cache_key}")
            try:
                sun_data = json.loads(cached_data)
            except json.JSONDecodeError:
                logger.warning("Error decoding cached data, fetching from API.")
                sun_data = None

    if sun_data is None:
        logger.info(f"Cache MISS or data error, fetching from API for key: {cache_key}")
        try:
            with tracer.start_span("sunrisesunset-api-call"):
                params = {"lat": lat, "lng": lon}
                if date_param:
                    params["date"] = date_param
                r = requests.get(SUNRISE_SUNSET_API_URL, params=params)
                r.raise_for_status()
                data = r.json()
                if data.get("status") == "OK":
                    sun_data = data["results"]
            if sun_data and redis_client:
                with tracer.start_span("redis-set"):
                    redis_client.set(cache_key, json.dumps(sun_data), ex=ttl)
                    logger.info(f"Cache SET for key: {cache_key} with TTL: {ttl}s")
        except Exception as e:
            logger.error(f"Error fetching sunspot data from API: {e}")
    return sun_data, resolved_date_str

# --- View ---
def sunspot_view(request):
    city_name = None
    with tracer.start_span("sunspot_view"):
        city = request.GET.get("city")
        lat = request.GET.get("lat")
        lon = request.GET.get("lon")
        date_param = request.GET.get("date")

        if city:
            city_name = city.strip()
            lat, lon = get_coordinates_from_city(city_name)
            if not lat or not lon:
                return JsonResponse({"error": f"Could not find coordinates for city: {city_name}"}, status=404)
        elif lat and lon:
            try:
                lat = str(float(lat))
                lon = str(float(lon))
                city_name = get_city_from_coordinates(lat, lon)
            except ValueError:
                return JsonResponse({"error": "Invalid lat/lon format"}, status=400)
        else:
            return JsonResponse({"error": "Missing city or lat/lon"}, status=400)

        sun_data, resolved_date_str = get_sunspot(lat, lon, date_param)
        if sun_data:
            if not city_name:
                city_name = f"Location {lat}, {lon}"
            return JsonResponse({
                "city": city_name,
                "latitude": lat,
                "longitude": lon,
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
    logger.info("Starting Sunspot Django backend on http://0.0.0.0:8000/api/sunspot")
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])