import os
import requests
from flask import Flask
from jaeger_client import Config
from flask_opentracing import FlaskTracing

app = Flask(__name__)

# Jaeger tracer initialization
def initialize_tracer():
    config = Config(
        config={
            'sampler': {'type': 'const', 'param': 1},
            'logging': True,
            'local_agent': {
                'reporting_host': 'jaeger-collector.tracing.svc',
                'reporting_port': 6831,
            },
        },
        service_name='flask-counter-frontend',
        validate=True,
    )
    return config.initialize_tracer()

# Initialize tracer and FlaskTracing
jaeger_tracer = initialize_tracer()
tracing = FlaskTracing(jaeger_tracer, True, app)

# Business logic
def get_counter(counter_endpoint):
    with jaeger_tracer.start_span('get_counter') as span:
        response = requests.get(counter_endpoint)
        span.set_tag('http.status_code', response.status_code)
        return response.text

def increase_counter(counter_endpoint):
    with jaeger_tracer.start_span('increase_counter') as span:
        response = requests.post(counter_endpoint)
        span.set_tag('http.status_code', response.status_code)
        return response.text

@app.route('/last')
def last():
    counter_service = os.environ.get('COUNTER_ENDPOINT', "https://localhost:8000")
    counter_endpoint = f'{counter_service}/api/counter'
    counter = get_counter(counter_endpoint)
    return f"\nLast visitor number: {counter}\n\n"

@app.route('/next')
def next():
    counter_service = os.environ.get('COUNTER_ENDPOINT', "https://localhost:8000")
    counter_endpoint = f'{counter_service}/api/counter'
    counter = increase_counter(counter_endpoint)
    return f"\nNext visitor number: {counter}\n\n"

# Graceful shutdown
@app.teardown_appcontext
def close_tracer(exception):
    global jaeger_tracer
    if jaeger_tracer:
        try:
            jaeger_tracer.close()
        except RuntimeError as e:
            # ignore the “no current event loop in thread” error
            if "no current event loop" in str(e):
                pass
            else:
                raise

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
