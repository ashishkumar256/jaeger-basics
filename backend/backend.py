import os, sys, logging
from django.conf import settings
from django.http import JsonResponse, HttpResponseNotFound
from django.urls import path
from django.core.management import execute_from_command_line
from opentelemetry.instrumentation.django import DjangoInstrumentor

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("hello")

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
        logger.info("✅ Django settings configured.")
    else:
        logger.info("⚠️ Django already configured.")

# --- Views ---
def hello_view(request):
    return JsonResponse({"message": "Hello, world!"})

def not_found_view(request, *args, **kwargs):
    return HttpResponseNotFound("404 Not Found")

urlpatterns = [
    path("api/hello", hello_view),
    path("", not_found_view),
]

# --- Entry point ---
if __name__ == "__main__":
    logger.info("🚀 Starting Hello Django (auto OpenTelemetry)...")

    setup_django()

    # ✅ Auto-instrument Django (uses env vars only)
    DjangoInstrumentor().instrument()

    # 🟢 Run Django normally — OpenTelemetry will handle tracing automatically
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])