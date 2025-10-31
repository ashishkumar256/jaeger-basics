FROM python:3.9-alpine

WORKDIR /app

COPY backend.py .

RUN pip install --no-cache-dir \
    django==5.2.7 \
    jaeger-client==4.8.0 \
    django-opentracing==1.1.0 \
    redis==7.0.1 \
    requests==2.32.5 \
    tornado==6.5.2 \
    python-dateutil==2.9.0.post0

EXPOSE 8000

CMD ["python", "backend.py"]