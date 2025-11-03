import sys
import logging
import types
import os

# ------------- Django settings MUST be defined BEFORE importing Django ---------

# Create a dynamic module = "settings"
settings = types.ModuleType("settings")

from django.core.management.utils import get_random_secret_key

# Assign Django settings into the module
settings.DEBUG = False
settings.SECRET_KEY = get_random_secret_key()       # ✅ auto-generate
settings.ALLOWED_HOSTS = ["*"]                      # ✅ required when DEBUG=False
settings.ROOT_URLCONF = "__main__"                  # ✅ URLs are defined in this file
settings.INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

# Register settings module so Django sees it
sys.modules["settings"] = settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

# --------------------- Safe to import Django now -------------------------------

from django.http import JsonResponse, HttpResponseNotFound
from django.urls import path
from django.core.management import execute_from_command_line

# ------------------------- Logging (optional) -----------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("hello")

# ----------------------------- Views --------------------------------------------

def hello_view(request):
    return JsonResponse({"message": "Hello, world!"})

def not_found_view(request, *args, **kwargs):
    return HttpResponseNotFound("404 Not Found")

# ----------------------------- URL patterns -------------------------------------

urlpatterns = [
    path("api/hello", hello_view),
    path("", not_found_view),
]

# ----------------------------- Entry point --------------------------------------

if __name__ == "__main__":
    logger.info("🚀 Starting Hello Django backend...")
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])