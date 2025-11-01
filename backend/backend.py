import os, sys
import logging
from django.conf import settings
from django.http import JsonResponse, HttpResponseNotFound
from django.urls import path
from django.core.management import execute_from_command_line

# --- OpenTelemetry imports ---
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("hello")

# --- OpenTelemetry setup ---
def setup_tracing():
    """Initializes OpenTelemetry TracerProvider and instruments Django using env-var driven config."""
    try:
        # Instrument Django (must come after settings.configure)
        DjangoInstrumentor().instrument()

        # Create Resource without explicitly hard-coding service name.
        # The SDK will use OTEL_SERVICE_NAME or OTEL_RESOURCE_ATTRIBUTES internally.
        resource = Resource.create({})

        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # Create exporter: the OTLP exporter will pick up endpoint and settings via env vars.
        exporter = OTLPSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))

        logger.info("✅ OpenTelemetry tracing initialized.")
        # Optionally log the resolved endpoint and service name from env:
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        if endpoint:
            logger.info(f"   → OTLP endpoint: {endpoint}")
        svc = os.getenv("OTEL_SERVICE_NAME")
        if svc:
            logger.info(f"   → Service name from env: {svc}")
        else:
            logger.info("   → Service name not set in env; default will be applied by SDK.")

    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize tracing: {e}")
        DjangoInstrumentor().uninstrument()

# --- Django setup ---
def setup_django():
    """Configures Django settings including ROOT_URLCONF and ALLOWED_HOSTS."""
    if not settings.configured:
        settings.configure(
            DEBUG=False,
            ROOT_URLCONF=__name__,
            ALLOWED_HOSTS=["*"],
            INSTALLED_APPS=[
                "opentelemetry.instrumentation.django",
            ],
        )
        logger.info("✅ Django settings configured successfully.")
    else:
        logger.info("⚠️ Django settings already configured, skipping reconfiguration.")

# --- Views ---
def hello_view(request):
    """Simple view that returns a JSON message and creates a custom span."""
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("hello-view-span"):
        return JsonResponse({"message": "Hello, world!"})

def not_found_view(request, *args, **kwargs):
    """Custom 404 handler for the root URL."""
    return HttpResponseNotFound("404 Not Found")

# --- URL patterns ---
urlpatterns = [
    path("api/hello", hello_view),
    path("", not_found_view),
]

# --- Entry point ---
if __name__ == "__main__":
    logger.info("🚀 Starting Hello Django backend with OpenTelemetry tracing...")

    setup_django()
    setup_tracing()

    try:
        execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
    except Exception as e:
        logger.error(f"❌ Django failed to start: {e}")
        logger.info("🔁 Fallback: Running simple HTTP server...")
        import http.server
        import socketserver

        PORT = 8000
        Handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            logger.info(f"🌐 Fallback HTTP server serving at port {PORT}")
            httpd.serve_forever()