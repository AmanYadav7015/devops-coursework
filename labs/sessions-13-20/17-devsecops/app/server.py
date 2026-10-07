import os

import requests
import yaml
from flask import Flask, jsonify, request

from app import SERVICE_NAME
from app.claims import (
    ClaimError,
    fingerprint,
    issue_reference,
    price_claim,
    summarise,
    validate_claim,
)

app = Flask(__name__)

APP_VERSION = os.environ.get("APP_VERSION", "0.0.0-dev")
GIT_COMMIT = os.environ.get("GIT_COMMIT", "unknown")
TOKEN_SALT = os.environ.get("CLAIM_TOKEN_SALT", "")
FX_ENDPOINT = os.environ.get("FX_ENDPOINT", "")


@app.get("/health")
def health():
    return jsonify({"service": SERVICE_NAME, "status": "ok"})


@app.get("/version")
def version():
    return jsonify(
        {
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "commit": GIT_COMMIT,
            "salt_configured": bool(TOKEN_SALT),
        }
    )


@app.post("/claims/validate")
def claims_validate():
    try:
        clean = validate_claim(request.get_json(silent=True))
    except ClaimError as exc:
        return jsonify({"error": exc.detail}), 400
    return jsonify(
        {
            "valid": True,
            "employee": clean["employee"],
            "category": clean["category"],
            "amount": float(clean["amount"]),
            "receipts": clean["receipts"],
        }
    )


@app.post("/claims/price")
def claims_price():
    payload = request.get_json(silent=True)
    try:
        priced = price_claim(payload)
        priced["fingerprint"] = fingerprint(payload, TOKEN_SALT)
        priced["reference"] = issue_reference()
    except ClaimError as exc:
        return jsonify({"error": exc.detail}), 400
    return jsonify(priced)


@app.post("/claims/batch")
def claims_batch():
    payload = request.get_json(silent=True)
    claims = payload.get("claims") if isinstance(payload, dict) else None
    try:
        return jsonify(summarise(claims))
    except ClaimError as exc:
        return jsonify({"error": exc.detail}), 400


@app.post("/policy/apply")
def policy_apply():
    document = request.get_data(as_text=True)
    try:
        parsed = yaml.safe_load(document)
    except yaml.YAMLError:
        return jsonify({"error": "policy document is not valid yaml"}), 400
    if not isinstance(parsed, dict):
        return jsonify({"error": "policy document must be a mapping"}), 400
    return jsonify({"applied": sorted(parsed.keys()), "entries": len(parsed)})


@app.get("/fx")
def fx():
    if not FX_ENDPOINT:
        return jsonify({"error": "no upstream rate service configured"}), 503
    try:
        upstream = requests.get(FX_ENDPOINT, timeout=3)
        upstream.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "upstream rate service unavailable"}), 502
    return jsonify({"source": FX_ENDPOINT, "rate": upstream.json()})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5017")))
