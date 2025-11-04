import sys
import logging
import django
from django.conf import settings
from django.core.management import execute_from_command_line
from django.http import HttpResponse
from django.urls import path

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

logger.info("Starting Django application with OpenTelemetry auto-tracing")

# Configure settings directly if not configured
if not settings.configured:
    logger.info("Configuring Django settings")
    settings.configure(
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=['*'],
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        MIDDLEWARE=[
            'django.middleware.common.CommonMiddleware',
        ],
    )

django.setup()

# Force override settings after setup (necessary due to OpenTelemetry)
settings.DEBUG = True
settings.ALLOWED_HOSTS = ['*']

logger.info(f"Django setup complete - DEBUG: {settings.DEBUG}, ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")

# View
def hello_world(request):
    logger.info(f"Hello World view called - Method: {request.method}, Path: {request.path}")
    return HttpResponse("Hello, World!")

# URL configuration
urlpatterns = [
    path('', hello_world),
    path('api/hello', hello_world),
]

if __name__ == '__main__':
    logger.info("Starting Django development server on 0.0.0.0:8000")
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])