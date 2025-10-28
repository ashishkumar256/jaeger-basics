import os, sys, requests
from django.conf import settings
from django.http import JsonResponse
from django.urls import path
from django.core.management import execute_from_command_line
from jaeger_client import Config
from django_opentracing.middleware import OpenTracingMiddleware
from django_opentracing import DjangoTracer

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
        service_name='django-sunspot-backend',
        validate=True,
    )
    return config.initialize_tracer()

tracer = initialize_tracer()
django_tracer = DjangoTracer(tracer)

# --- Core logic ---
def get_coordinates_from_city(city):
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search", params={
            "city": city, "format": "json", "limit": 1
        }, headers={"User-Agent": "SunspotMinimal/1.0"})
        r.raise_for_status()
        data = r.json()
        if data and data[0].get("lat") and data[0].get("lon"):
            return data[0]["lat"], data[0]["lon"]
    except:
        pass
    return None, None

def get_sunspot(lat, lon):
    try:
        r = requests.get("https://api.sunrisesunset.io/json", params={"lat": lat, "lng": lon})
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "OK":
            return data["results"]
    except:
        pass
    return None

# --- View ---
def sunspot_view(request):
    with tracer.start_span("sunspot_view"):
        city = request.GET.get("city")
        lat = request.GET.get("lat")
        lon = request.GET.get("lon")

        if city:
            lat, lon = get_coordinates_from_city(city.strip())
            if not lat or not lon:
                return JsonResponse({"error": f"Could not find coordinates for city: {city}"}, status=404)
        elif lat and lon:
            try:
                lat = str(float(lat))
                lon = str(float(lon))
            except ValueError:
                return JsonResponse({"error": "Invalid lat/lon format"}, status=400)
        else:
            return JsonResponse({"error": "Missing city or lat/lon"}, status=400)

        sun_data = get_sunspot(lat, lon)
        if sun_data:
            return JsonResponse({
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