FROM python:3.12-alpine

RUN pip3 install --no-cache-dir  flask six requests jaeger-client flask-opentracing

WORKDIR /app

COPY frontend.py .

ENV FLASK_APP frontend

EXPOSE 5000

CMD flask run --host=0.0.0.0 --port=5000
