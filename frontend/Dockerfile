FROM python:3.9-alpine

RUN pip install --no-cache-dir \
    flask==3.1.2 \
    six==1.16.0 \
    requests==2.32.5 \
    jaeger-client==4.8.0 \
    flask-opentracing==0.1.7

WORKDIR /app

COPY frontend.py .

ENV FLASK_APP frontend

EXPOSE 5000

CMD ["python", "frontend.py"]
