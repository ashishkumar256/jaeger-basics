FROM python:3.12-alpine

WORKDIR /app

COPY backend.py .

RUN pip install --no-cache-dir django jaeger-client opentracing opentracing-instrumentation

EXPOSE 8000

CMD ["python", "backend.py"]