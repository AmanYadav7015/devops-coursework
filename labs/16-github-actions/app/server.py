"""HTTP surface for the Yatri fare service."""

import os

from flask import Flask, jsonify, request

from app import APP_NAME
from app.fare import TripError, apply_coupon, compute_fare, split_fare

APP_VERSION = os.environ.get("APP_VERSION", "0.0.0-local")
GIT_COMMIT = os.environ.get("GIT_COMMIT", "unknown")

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify(status="ok", service=APP_NAME), 200


@app.get("/version")
def version():
    return jsonify(service=APP_NAME, version=APP_VERSION, commit=GIT_COMMIT), 200


@app.post("/fare")
def fare():
    payload = request.get_json(silent=True) or {}
    try:
        amount = compute_fare(
            float(payload.get("distance_km", 0)),
            float(payload.get("duration_min", 0)),
            float(payload.get("surge", 1.0)),
            bool(payload.get("night", False)),
        )
        if payload.get("coupon"):
            amount = apply_coupon(amount, payload["coupon"])
        riders = int(payload.get("riders", 1))
        return jsonify(total=amount, currency="INR", per_rider=split_fare(amount, riders)), 200
    except TripError as exc:
        return jsonify(error=str(exc)), 400
    except (TypeError, ValueError) as exc:
        return jsonify(error="invalid request payload: " + str(exc)), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8080")))
