"""Tiny two-role demo service used for the Session 20 monitoring/observability lab.

ROLE=web        -> public API (/order calls the inventory service, /work burns CPU)
ROLE=inventory  -> backend called by web (/check simulates a slow DB lookup)

Exposes all three signals:
  metrics -> Prometheus format on /metrics (prometheus_client)
  logs    -> one JSON line per request on stdout (picked up by kubectl logs / Alloy -> Loki)
  traces  -> OpenTelemetry spans exported over OTLP/HTTP (to Jaeger) when
             OTEL_EXPORTER_OTLP_ENDPOINT is set
"""
import hashlib
import json
import logging
import os
import random
import sys
import time

import requests
from flask import Flask, Response, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

ROLE = os.getenv("ROLE", "web")
VERSION = os.getenv("APP_VERSION", "1.0.0")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://shop-inventory:8000")
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.05"))
SERVICE_NAME = f"shop-{ROLE}"

# ---------- tracing (optional) ----------
tracer = None
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME,
                                                        "service.version": VERSION}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(SERVICE_NAME)
    RequestsInstrumentor().instrument()

app = Flask(__name__)
if tracer is not None:
    FlaskInstrumentor().instrument_app(app, excluded_urls="metrics,healthz,readyz")

# ---------- logging: JSON lines on stdout ----------
log = logging.getLogger(SERVICE_NAME)
log.setLevel(logging.INFO)
_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(logging.Formatter("%(message)s"))
log.addHandler(_h)
logging.getLogger("werkzeug").setLevel(logging.WARNING)


def current_trace_id():
    if tracer is None:
        return None
    from opentelemetry import trace
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else None


# ---------- metrics ----------
REQUESTS = Counter("http_requests_total", "HTTP requests", ["app", "method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["app", "path"],
                    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
ORDERS = Counter("shop_orders_total", "Orders placed", ["result"])
IN_FLIGHT = Gauge("http_requests_in_flight", "Requests currently being served", ["app"])
INFO = Gauge("app_info", "Static build info", ["app", "version"])
INFO.labels(SERVICE_NAME, VERSION).set(1)


@app.before_request
def _start():
    g.start = time.perf_counter()
    IN_FLIGHT.labels(SERVICE_NAME).inc()


@app.after_request
def _finish(resp):
    IN_FLIGHT.labels(SERVICE_NAME).dec()
    path = request.url_rule.rule if request.url_rule else "unmatched"
    if path in ("/metrics", "/healthz", "/readyz"):
        return resp
    elapsed = time.perf_counter() - g.start
    REQUESTS.labels(SERVICE_NAME, request.method, path, resp.status_code).inc()
    LATENCY.labels(SERVICE_NAME, path).observe(elapsed)
    level = "ERROR" if resp.status_code >= 500 else "INFO"
    log.info(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "level": level,
                         "service": SERVICE_NAME, "method": request.method, "path": request.path,
                         "status": resp.status_code, "duration_ms": round(elapsed * 1000, 1),
                         "trace_id": current_trace_id()}))
    return resp


# ---------- health ----------
@app.get("/healthz")
def healthz():
    return "ok\n"


@app.get("/readyz")
def readyz():
    return "ready\n"


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


# ---------- business endpoints ----------
@app.get("/")
def index():
    return jsonify(service=SERVICE_NAME, version=VERSION, pod=os.getenv("HOSTNAME"))


@app.get("/work")
def work():
    """Burn CPU for ?ms= milliseconds (used by the load generator to trigger the CPU alert)."""
    ms = int(request.args.get("ms", "100"))
    end = time.perf_counter() + ms / 1000
    n = 0
    while time.perf_counter() < end:
        hashlib.sha256(str(n).encode()).hexdigest()
        n += 1
    return jsonify(hashes=n)


@app.get("/order")
def order():
    item = random.choice(["keyboard", "mouse", "monitor", "laptop"])
    r = requests.get(f"{INVENTORY_URL}/check", params={"item": item}, timeout=3)
    if r.status_code != 200:
        ORDERS.labels("failed").inc()
        log.info(json.dumps({"level": "ERROR", "service": SERVICE_NAME, "msg": "inventory check failed",
                             "item": item, "upstream_status": r.status_code,
                             "trace_id": current_trace_id()}))
        return jsonify(error="inventory unavailable", item=item), 502
    ORDERS.labels("ok").inc()
    return jsonify(order="placed", item=item, stock=r.json()["stock"])


@app.get("/check")
def check():
    item = request.args.get("item", "unknown")
    delay = random.uniform(0.02, 0.15)
    if tracer is not None:
        with tracer.start_as_current_span("db.query") as span:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.statement", "SELECT stock FROM inventory WHERE item = $1")
            span.set_attribute("app.item", item)
            time.sleep(delay)
    else:
        time.sleep(delay)
    if random.random() < ERROR_RATE:
        return jsonify(error="db timeout"), 500
    return jsonify(item=item, stock=random.randint(0, 50))


if __name__ == "__main__":
    log.info(json.dumps({"level": "INFO", "service": SERVICE_NAME, "msg": "starting", "version": VERSION}))
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), threaded=True)
