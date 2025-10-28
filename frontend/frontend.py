import os
import requests
from flask import Flask, request
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
                'reporting_host': 'jaeger-agent.tracing.svc',
                'reporting_port': 6831,
            },
        },
        service_name='flask-sunspot-frontend',
        validate=True,
    )
    return config.initialize_tracer()

# Initialize tracer and FlaskTracing
jaeger_tracer = initialize_tracer()
tracing = FlaskTracing(jaeger_tracer, True, app)

# Business logic
def fetch_sunspot(endpoint, span_name):
    with jaeger_tracer.start_span(span_name) as span:
        try:
            response = requests.get(endpoint)
            span.set_tag('http.status_code', response.status_code)
            response.raise_for_status()
            return response.text, response.status_code
        except requests.exceptions.RequestException as e:
            span.set_tag('error', True)
            return f"Error fetching sun spot timings: {e}", 503

@app.route('/sunspot/city/<city_name>')
def sunspot_by_city(city_name):
    sunspot_service = os.environ.get('SUNSPOT_BACKEND_ENDPOINT', "http://localhost:8000")
    endpoint = f'{sunspot_service}/api/sunspot?city={city_name}'
    result, status = fetch_sunspot(endpoint, 'get_sunspot_by_city')
    return result, status

@app.route('/sunspot/coords')
def sunspot_by_coords():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        return "Missing 'lat' or 'lon' query parameters.\n", 400
    sunspot_service = os.environ.get('SUNSPOT_BACKEND_ENDPOINT', "http://localhost:8000")
    endpoint = f'{sunspot_service}/api/sunspot?lat={lat}&lon={lon}'
    result, status = fetch_sunspot(endpoint, 'get_sunspot_by_coords')
    return result, status

# Graceful shutdown
@app.teardown_appcontext
def close_tracer(exception):
    global jaeger_tracer
    if jaeger_tracer:
        try:
            jaeger_tracer.close()
        except RuntimeError as e:
            if "no current event loop" in str(e):
                pass
            else:
                raise

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))