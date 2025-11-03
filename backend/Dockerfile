FROM python:3.10-alpine

WORKDIR /app
COPY backend.py .

RUN pip install --no-cache-dir \
    django==5.2.7 \
    opentelemetry-distro==0.46b0 \
    opentelemetry-exporter-otlp==1.38.0 \
    opentelemetry-instrumentation-django==0.59b0

RUN opentelemetry-bootstrap -a install

EXPOSE 8000

CMD ["opentelemetry-instrument", "python", "backend.py"]