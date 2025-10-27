# Use a Python base image, suitable for running Django
FROM python:3.11-slim-buster

# Install build dependencies temporarily for installing Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /usr/src/backend

# Install all required Python packages (Django, Gunicorn, Tracing)
# These versions match the necessary components for the backend.py script.
RUN pip install --no-cache-dir \
    Django==4.2.0 \
    gunicorn==20.1.0 \
    jaeger-client==4.4.0 \
    django-opentracing==0.2.0 \
    six==1.16.0

# Copy the single application file
COPY backend.py /usr/src/backend/

# Set environment variable for unbuffered python output
ENV PYTHONUNBUFFERED 1

# Expose the port
EXPOSE 8000

# Run the application using Gunicorn.
# It targets the 'application' WSGI callable within the 'backend.py' module.
CMD gunicorn backend:application --bind 0.0.0.0:8000
