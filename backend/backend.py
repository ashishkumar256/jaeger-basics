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
def setup_tracing():
    try:
        resource = Resource(attributes={SERVICE_NAME: "hello-django"})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint="http://localhost:4318/v1/traces",  # adjust if otel-agent URL differs
            timeout=5,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        DjangoInstrumentor().instrument()
        logger.info("✅ OpenTelemetry tracing initialized (to otel-agent).")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize tracing: {e}")
        DjangoInstrumentor().uninstrument()

# --- Django setup ---
def setup_django():
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
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("hello-view-span"):
        return JsonResponse({"message": "Hello, world!"})

def not_found_view(request, *args, **kwargs):
    return HttpResponseNotFound("404 Not Found")

# --- URL patterns ---
urlpatterns = [
    path("api/hello", hello_view),
    path("", not_found_view),
]

# --- Entry point ---
if __name__ == "__main__":
    logger.info("🚀 Starting Hello Django backend with OpenTelemetry tracing...")
    setup_tracing()
    setup_django()

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
