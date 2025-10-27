from random import randint
from time import sleep
from django.conf import settings
from django.http import HttpResponse
from django.urls import path
from django.core.management import execute_from_command_line

from jaeger_client import Config
from django_opentracing.middleware import DjangoTracing
from django_opentracing import DjangoTracer

# ---- Minimal Django setup ----
settings.configure(
    DEBUG=True,
    ROOT_URLCONF=__name__,
    ALLOWED_HOSTS=["*"],
    MIDDLEWARE=[
        'django_opentracing.middleware.OpenTracingMiddleware',
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
        service_name='django-counter-backend',
        validate=True,
    )
    return config.initialize_tracer()

jaeger_tracer = initialize_tracer()
django_tracing = DjangoTracing(DjangoTracer(jaeger_tracer))

# ---- Counter logic ----
counter_value = 1

def simulate_latency():
    """Simulate variable processing delay (1–3 seconds)."""
    sleep(randint(1, 3))

def get_counter():
    with jaeger_tracer.start_span('get_counter'):
        simulate_latency()
        return str(counter_value)

def increase_counter():
    global counter_value
    with jaeger_tracer.start_span('increase_counter'):
        simulate_latency()
        counter_value += 1
        return str(counter_value)

# ---- Django view ----
def counter_view(request):
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