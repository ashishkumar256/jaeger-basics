import sys
import logging

# ======================================================================
# 1. Django Imports
# ======================================================================
from django.conf import settings
from django.http import JsonResponse, HttpResponseNotFound
from django.urls import path
from django.core.management import execute_from_command_line

# ======================================================================
# 2. OpenTelemetry Imports
# ======================================================================
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor

# ======================================================================
# 3. Logging Setup
# ======================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("hello")

# ======================================================================
# 4. Django Configuration
# ======================================================================
def setup_django():
    """Configure minimal Django settings."""
    settings.configure(
        DEBUG=False,
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["*"],
        MIDDLEWARE=[
            "opentelemetry.instrumentation.django.middleware.OpenTelemetryMiddleware",
        ],
        INSTALLED_APPS=[
            "opentelemetry.instrumentation.django",
        ],
    )


# ======================================================================
# 5. OpenTelemetry (Tracing) Setup
# ======================================================================
def setup_tracing():
    """Configure OpenTelemetry tracing with fallback if OTEL agent is unreachable."""
    resource = Resource(attributes={SERVICE_NAME: "hello-django"})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    try:
        exporter = OTLPSpanExporter(
            endpoint="http://localhost:4318/v1/traces",  # DaemonSet hostPort
            timeout=5,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("✅ OpenTelemetry tracing initialized (to otel-agent).")
    except Exception as e:
        logger.warning(f"⚠️  OpenTelemetry exporter setup failed: {e}. Running without tracing.")

    DjangoInstrumentor().instrument()


# ======================================================================
# 6. Django Views
# ======================================================================
def hello_view(request):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("hello-view-span"):
        return JsonResponse({"message": "Hello, world!"})


def not_found_view(request, *args, **kwargs):
    return HttpResponseNotFound("404 Not Found")


# ======================================================================
# 7. URL Patterns
# ======================================================================
urlpatterns = [
    path("hello", hello_view),
    path("", not_found_view),
]


# ======================================================================
# 8. Entry Point
# ======================================================================
if __name__ == "__main__":
    logger.info("🚀 Starting Hello Django backend with OpenTelemetry tracing...")
    setup_django()     # ✅ configure Django FIRST
    setup_tracing()    # ✅ then instrument tracing
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])