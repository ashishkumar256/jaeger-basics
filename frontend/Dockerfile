FROM python:3.9-alpine

RUN pip3 install --no-cache-dir flask six requests jaeger-client flask-opentracing

WORKDIR /app

COPY frontend.py .

ENV FLASK_APP frontend

EXPOSE 5000

CMD ["python", "frontend.py"]
