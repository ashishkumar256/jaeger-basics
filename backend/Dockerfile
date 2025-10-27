FROM python:3.9-alpine

WORKDIR /app

COPY backend.py .

RUN pip install --no-cache-dir django jaeger-client django-opentracing 'tornado>=4.0.0,<5.0.0'

EXPOSE 8000

CMD ["python", "backend.py"]