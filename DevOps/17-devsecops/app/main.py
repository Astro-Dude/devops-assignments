"""hw-devsecops: a small Flask service used to exercise the Session 17 pipeline.

Endpoints
---------
GET  /                  HTML landing page
GET  /health            liveness probe   (process is up)
GET  /ready             readiness probe  (app is able to serve)
GET  /api/status        build/runtime metadata
GET  /api/greet/<name>  JSON greeting (input length-limited)
POST /api/calculate     {"a": 6, "b": 3, "operation": "multiply"}
"""

import datetime
import os
import platform
import sys

from flask import Flask, jsonify, render_template, request

APP_NAME = "hw-devsecops"
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
GIT_SHA = os.environ.get("GIT_SHA", "local")
MAX_NAME_LEN = 64

_START = datetime.datetime.now(datetime.timezone.utc)

app = Flask(__name__)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@app.after_request
def security_headers(resp):
    """Defence-in-depth HTTP headers on every response."""
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
    )
    return resp


@app.route("/")
def home():
    return render_template("index.html", version=APP_VERSION, sha=GIT_SHA)


@app.route("/health")
def health():
    return jsonify(status="healthy", timestamp=_now())


@app.route("/ready")
def ready():
    return jsonify(status="ready", timestamp=_now())


@app.route("/api/status")
def status():
    uptime = (datetime.datetime.now(datetime.timezone.utc) - _START).total_seconds()
    return jsonify(
        app=APP_NAME,
        version=APP_VERSION,
        git_sha=GIT_SHA,
        python_version=sys.version.split()[0],
        platform=platform.system(),
        uptime_seconds=round(uptime, 1),
        status="running",
    )


@app.route("/api/greet/<name>")
def greet(name: str):
    if len(name) > MAX_NAME_LEN or not name.replace("-", "").replace(" ", "").isalnum():
        return jsonify(error="name must be 1-64 letters/digits/spaces/hyphens"), 400
    return jsonify(message=f"Hello, {name}! Your pipeline passed the security gate.", name=name)


_OPS = {
    "add": lambda a, b: a + b,
    "subtract": lambda a, b: a - b,
    "multiply": lambda a, b: a * b,
    "divide": lambda a, b: a / b,
}


@app.route("/api/calculate", methods=["POST"])
def calculate():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON object body required"), 400
    op = data.get("operation", "add")
    if op not in _OPS:
        return jsonify(error=f"unknown operation '{op}'", valid=sorted(_OPS)), 400
    try:
        a, b = float(data["a"]), float(data["b"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="fields 'a' and 'b' must be numbers"), 400
    if op == "divide" and b == 0:
        return jsonify(error="division by zero"), 400
    return jsonify(a=a, b=b, operation=op, result=_OPS[op](a, b))


@app.errorhandler(404)
def not_found(_e):
    return jsonify(error="route not found"), 404


if __name__ == "__main__":  # pragma: no cover - local dev only; production uses gunicorn
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "9301")))
