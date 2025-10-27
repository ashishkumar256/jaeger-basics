from random import randint
from time import sleep
from django.conf import settings
from django.http import HttpResponse
from django.urls import path
from django.core.management import execute_from_command_line

# Jaeger / OpenTracing imports
from jaeger_client import Config
from opentracing_instrumentation.client_hooks import install_all_patches
import opentracing

# ---- Minimal Django setup ----
settings.configure(
    DEBUG=True,
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=["*"],
)

# ---- Initialize Jaeger tracer ----
def init_tracer():
    config = Config(
        config={
            'sampler': {'type': 'const', 'param': 1},
            'logging': True,
            'reporter_batch_size': 1,
        },
        service_name="backend",
    )
    tracer = config.initialize_tracer()
    install_all_patches()  # Patch requests, etc.
    return tracer

tracer = init_tracer()
opentracing.global_tracer = tracer

# ---- Counter logic ----
counter_value = 1

def simulate_latency():
    """Simulate variable processing delay (1–3 seconds)."""
    sleep(randint(1, 3))

def get_counter():
    with tracer.start_active_span("get_counter"):
        simulate_latency()
        return str(counter_value)

def increase_counter():
    global counter_value
    with tracer.start_active_span("increase_counter"):
        simulate_latency()
        counter_value += 1
        return str(counter_value)

# ---- Django view ----
def counter_view(request):
    with tracer.start_active_span("counter_view") as scope:
        if request.method == "GET":
            return HttpResponse(get_counter())
        elif request.method == "POST":
            return HttpResponse(increase_counter())
        else:
            return HttpResponse("Method not allowed", status=405)

# ---- URL pattern ----
urlpatterns = [
    path("api/counter", counter_view),
]

# ---- Run server ----
if __name__ == "__main__":
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
