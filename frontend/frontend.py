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
        service_name='sunspot-flask-frontend',
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
            # Injecting trace context into the request headers for distributed tracing
            headers = {}
            tracing.tracer.inject(span.context, 'http_headers', headers)
            
            response = requests.get(endpoint, headers=headers)
            span.set_tag('http.status_code', response.status_code)
            response.raise_for_status()
            return response.text, response.status_code
        except requests.exceptions.RequestException as e:
            span.set_tag('error', True)
            span.log_kv({'event': 'error', 'message': str(e)})
            return f"Error fetching sun spot timings: {e}", 503

@app.route('/sunspot')
def sunspot_combined_query():
    """Route to get sunspot data using either 'city' or 'lat'/'lon' query parameters."""
    
    city = request.args.get('city')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    sunspot_service = os.environ.get('SUNSPOT_BACKEND_ENDPOINT', "http://localhost:8000")
    endpoint = None
    span_name = None

    if city:
        # Querying by city
        # Backend service expects query parameter '?city='
        endpoint = f'{sunspot_service}/api/sunspot?city={city}' 
        span_name = 'get_sunspot_by_city_query'
    elif lat and lon:
        # Querying by coordinates
        # Backend service expects query parameters '?lat=' and '&lon='
        endpoint = f'{sunspot_service}/api/sunspot?lat={lat}&lon={lon}'
        span_name = 'get_sunspot_by_coords_query'
    else:
        # Missing required parameters
        return "Missing 'city' or 'lat'/'lon' query parameters.\n", 400

    result, status = fetch_sunspot(endpoint, span_name)
    return result, status

# Graceful shutdown
@app.teardown_appcontext
def close_tracer(exception):
    global jaeger_tracer
    if jaeger_tracer:
        try:
            jaeger_tracer.close()
        except RuntimeError as e:
            print(f"WARNING: RuntimeError during Jaeger tracer close: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))