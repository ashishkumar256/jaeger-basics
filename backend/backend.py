# This script sets up a minimal, self-contained Django application.
# It includes the Jaeger tracing configuration and the counter API logic.

# --- 1. Imports ---
import os
from random import randint
from time import sleep

# Django Core Imports
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.urls import path
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ImproperlyConfigured

# Tracing Imports
from jaeger_client import Config
# We import the middleware here to ensure the name is available, 
# although it's referenced by string in settings.configure()
from django_opentracing.middleware import OpenTracingMiddleware 

# --- 2. Global Counter State ---
# NOTE: This global variable is NOT thread-safe for production use (use Firestore/Redis).
global_counter_value = 1

def get_counter():
    """Retrieves the current counter value."""
    return str(global_counter_value)

def increase_counter():
    """Increments the counter value after a random sleep."""
    global global_counter_value
    
    # Introduce random delay (1-3 seconds)
    sleep(randint(1, 3)) 
    
    global_counter_value += 1
    return str(global_counter_value)

# --- 3. Django View ---

@require_http_methods(["GET", "POST"])
def counter_api(request):
    """
    Handles GET to retrieve the counter and POST to increment it.
    
    Tracing is automatically applied by the OpenTracingMiddleware.
    We create child spans using the tracer attached to the request's tracing_span.
    """
    
    # Safely get the tracer from the request or the global settings (fallback)
    tracer = getattr(request, 'tracing_span', None).tracer if hasattr(request, 'tracing_span') else settings.OPENTRACING_TRACER
    
    if request.method == 'GET':
        if tracer:
            with tracer.start_span('get_counter_operation', child_of=getattr(request, 'tracing_span', None)) as span:
                span.set_tag('http.method', 'GET')
                return HttpResponse(get_counter())
        else:
            return HttpResponse(get_counter())
            
    elif request.method == 'POST':
        if tracer:
            with tracer.start_span('increase_counter_operation', child_of=getattr(request, 'tracing_span', None)) as span:
                span.set_tag('http.method', 'POST')
                return HttpResponse(increase_counter())
        else:
            return HttpResponse(increase_counter())
    
    return HttpResponse("Method not allowed", status=405)


# --- 4. Django Settings and Tracing Configuration ---

# Jaeger Configuration (mirrors the original Flask setup)
JAEGER_CONFIG = Config(
    config={
        'sampler': {
            'type': 'const',
            'param': 1
        },
        'logging': True,
        'reporter_batch_size': 1,
    },
    service_name="backend"
)

# Initialize the Tracer 
OPENTRACING_TRACER = JAEGER_CONFIG.initialize_tracer()

# Configure Django settings dynamically (required for a standalone script)
if not settings.configured:
    settings.configure(
        # Essential Settings
        DEBUG=True,
        SECRET_KEY='a-dummy-secret-key',
        
        # App and Middleware Configuration (important for tracing)
        INSTALLED_APPS=['django_opentracing'],
        ROOT_URLCONF='backend', # Points Django to the urlpatterns defined in this file
        MIDDLEWARE=['django_opentracing.middleware.OpenTracingMiddleware'],
        
        # Tracer Configuration (used by django-opentracing middleware)
        OPENTRACING_TRACER=OPENTRACING_TRACER,
    )

# --- 5. URL Routing ---

# Define the URL patterns for the application
urlpatterns = [
    path('api/counter', counter_api),
]


# --- 6. Application Setup and WSGI Hook ---

# Setup Django environment after configuration
try:
    from django import setup as django_setup
    django_setup()
except (ImproperlyConfigured, AttributeError):
    pass 

# Expose the WSGI application object for Gunicorn to use
application = get_wsgi_application()
