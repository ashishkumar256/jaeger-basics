import sys
import logging
from django.conf import settings
from django.core.management import execute_from_command_line
from django.http import JsonResponse, HttpResponseNotFound
from django.urls import path

# --- Logging (optional) ---
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
                "django.contrib.contenttypes",
                "django.contrib.auth",
            ],
        )
        logger.info("✅ Django settings configured.")

# --- Views ---
def hello_view(request):
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
    logger.info("🚀 Starting Hello Django backend...")

    setup_django()
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])