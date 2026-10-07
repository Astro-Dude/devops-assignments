"""HTTP API around the calculator (Flask)."""

import os
import socket

from flask import Flask, jsonify, request

from app import __version__
from app.calculator import OPERATIONS


def create_app():
    app = Flask(__name__)

    @app.get("/")
    def index():
        return jsonify(
            service="s16-calculator",
            version=__version__,
            git_sha=os.environ.get("GIT_SHA", "dev"),
            hostname=socket.gethostname(),
            operations=sorted(OPERATIONS),
        )

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/api/<operation>")
    def calculate(operation):
        func = OPERATIONS.get(operation)
        if func is None:
            return jsonify(error=f"unknown operation '{operation}'"), 404
        try:
            a = float(request.args["a"])
            b = float(request.args["b"])
        except KeyError as missing:
            return jsonify(error=f"missing query parameter {missing}"), 400
        except ValueError:
            return jsonify(error="a and b must be numbers"), 400
        try:
            result = func(a, b)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(operation=operation, a=a, b=b, result=result)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
