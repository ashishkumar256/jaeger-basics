import sys
import logging
from django.conf import settings
from django.http import JsonResponse, HttpResponseNotFound
from django.urls import path
from django.core.management import execute_from_command_line

# --- OpenTelemetry imports ---
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
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
# --- OpenTelemetry setup ---
def setup_tracing():
    """Initializes OpenTelemetry TracerProvider and instruments Django."""
    try:
        # Instrument Django (must come after settings.configure)
        DjangoInstrumentor().instrument()

        # 1️⃣ Dynamically determine OTLP endpoint
        otel_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",  # prefer explicit env var
            f"http://{os.getenv('HOST_IP', 'localhost')}:4318/v1/traces"  # fallback
        )

        # 2️⃣ Setup provider and exporter
        resource = Resource(attributes={SERVICE_NAME: "hello-django"})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otel_endpoint, timeout=5)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        logger.info(f"✅ OpenTelemetry tracing initialized (to {otel_endpoint}).")

    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize tracing: {e}")
        DjangoInstrumentor().uninstrument()


# --- Django setup ---
def setup_django():
    """Configures Django settings including ROOT_URLCONF and ALLOWED_HOSTS."""
    if not settings.configured:
        settings.configure(
            # Since we are running in production mode (or without Django project structure), 
            # DEBUG is False, which mandates setting ALLOWED_HOSTS.
            DEBUG=False,
            ROOT_URLCONF=__name__,
            # Allowing '0.0.0.0' for binding to all interfaces.
            ALLOWED_HOSTS = ["*"], 
            INSTALLED_APPS=[
                "opentelemetry.instrumentation.django",
            ],
        )
        logger.info("✅ Django settings configured successfully.")
    else:
        # This message indicates an ordering issue if it appears before tracing setup.
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
    
    # CRITICAL FIX: setup_django MUST be called first to configure 
    # settings (like ALLOWED_HOSTS) before any Django component 
    # (like the instrumentation) attempts to use them.
    setup_django()
    setup_tracing()
    
    try:
        # Start the Django development server
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