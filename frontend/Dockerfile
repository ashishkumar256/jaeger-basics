FROM python:3.12-alpine

RUN pip3 install --no-cache-dir  flask six requests flask_opentracing jaeger-client opentracing opentracing-instrumentation flask-opentracing requests-opentracing

WORKDIR /app

COPY frontend.py .

ENV FLASK_APP frontend

EXPOSE 5000

CMD flask run --host=0.0.0.0 --port=5000
