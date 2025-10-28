import os, sys, requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.urls import path, re_path
from django.core.management import execute_from_command_line
from jaeger_client import Config
import django_opentracing

# --- API Constants ---
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
SUNRISE_SPOT_URL = "https://api.sunrisesunset.io/json"

# ---- Minimal Django setup ----
settings.configure(
    DEBUG=True,
    ROOT_URLCONF=sys.modules[__name__],
    ALLOWED_HOSTS=["*"],
    MIDDLEWARE=[
        'django_opentracing.OpenTracingMiddleware',
    ],
)

# ---- Jaeger tracer setup ----
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
        service_name='django-sunspot-backend',
        validate=True,
    )
    return config.initialize_tracer()

tracer = initialize_tracer()
django_opentracing.tracer = tracer

# ---- Helper Functions ----
def get_coordinates_from_city(city_name_cleaned):
    headers = {'User-Agent': 'DjangoSunSpotApp/1.0'}
    params = {
        'city': city_name_cleaned,
        'format': 'json',
        'limit': 1
    }
    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data and data[0].get('lat') and data[0].get('lon'):
            return data[0]['lat'], data[0]['lon']
        else:
            return None, None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching coordinates: {e}")
        return None, None

def get_city_from_coordinates(lat, lon):
    headers = {'User-Agent': 'DjangoSunSpotApp/1.0'}
    params = {
        'lat': lat,
        'lon': lon,
        'format': 'json'
    }
    try:
        response = requests.get(NOMINATIM_REVERSE_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        address = data.get('address', {})
        return address.get('city') or address.get('town') or address.get('village') or address.get('state') or 'N/A'
    except requests.exceptions.RequestException as e:
        print(f"Error reverse geocoding: {e}")
        return 'N/A'

def get_sunspot_by_coords(lat, lon):
    params = {
        'lat': lat,
        'lng': lon
    }
    try:
        response = requests.get(SUNRISE_SPOT_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'OK':
            return data['results']
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching sun spot timings: {e}")
        return None

# ---- Views ----
def sunspot_by_city_view(request, city_name):
    with django_opentracing.tracer.start_active_span('sunspot_by_city_view'):
        city_searched = city_name.strip()
        lat, lon = get_coordinates_from_city(city_searched)
        if not lat or not lon:
            return JsonResponse({'error': f'Could not find coordinates for city: {city_searched}'}, status=404)

        sunspot = get_sunspot_by_coords(lat, lon)
        if sunspot:
            return JsonResponse({
                'city_searched': city_searched,
                'latitude': lat,
                'longitude': lon,
                'sun_data': sunspot
            }, status=200)
        else:
            return JsonResponse({'error': 'Could not retrieve sun spot timings data.'}, status=503)

def sunspot_by_coords_view(request):
    with django_opentracing.tracer.start_active_span('sunspot_by_coords_view'):
        lat = request.GET.get('lat')
        lon = request.GET.get('lon')
        if not lat or not lon:
            return JsonResponse({'error': 'Missing required query parameters: lat and lon'}, status=400)
        try:
            lat = str(float(lat))
            lon = str(float(lon))
        except ValueError:
            return JsonResponse({'error': 'Invalid format for latitude or longitude. Must be a number.'}, status=400)

        city = get_city_from_coordinates(lat, lon)
        sunspot = get_sunspot_by_coords(lat, lon)
        if sunspot:
            return JsonResponse({
                'city_searched': city,
                'latitude': lat,
                'longitude': lon,
                'sun_data': sunspot
            }, status=200)
        else:
            return JsonResponse({'error': 'Could not retrieve sun spot timings data.'}, status=503)

# ---- URL patterns ----
urlpatterns = [
    path("sunspot/coords", sunspot_by_coords_view),
    re_path(r"^sunspot/city/(?P<city_name>[\w\s\-]+)/?$", sunspot_by_city_view),
]

# ---- Run server ----
if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', __name__)
    try:
        execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
    except Exception as e:
        print(f"Error running Django server: {e}")