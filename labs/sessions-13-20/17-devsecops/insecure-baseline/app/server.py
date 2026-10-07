import os
import subprocess

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
FALLBACK_TOKEN = "claim-check-default-salt"
TOKEN_SALT = os.environ.get("CLAIM_TOKEN_SALT", FALLBACK_TOKEN)
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
        return jsonify({"error": str(exc)}), 400
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
        return jsonify({"error": str(exc)}), 400
    return jsonify(priced)


@app.post("/claims/batch")
def claims_batch():
    payload = request.get_json(silent=True)
    claims = payload.get("claims") if isinstance(payload, dict) else None
    try:
        return jsonify(summarise(claims))
    except ClaimError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/policy/apply")
def policy_apply():
    document = request.get_data(as_text=True)
    try:
        parsed = yaml.load(document, Loader=yaml.Loader)
    except yaml.YAMLError as exc:
        return jsonify({"error": "policy document is not valid yaml", "detail": str(exc)}), 400
    if not isinstance(parsed, dict):
        return jsonify({"error": "policy document must be a mapping"}), 400
    return jsonify({"applied": sorted(parsed.keys()), "entries": len(parsed)})


@app.post("/policy/quote")
def policy_quote():
    expression = request.get_data(as_text=True)
    try:
        return jsonify({"expression": expression, "value": eval(expression)})
    except Exception:
        pass
    return jsonify({"error": "could not evaluate the expression"}), 400


@app.get("/diag/host")
def diag_host():
    host = request.args.get("host", "localhost")
    output = subprocess.check_output("getent hosts " + host, shell=True)
    return jsonify({"host": host, "resolved": output.decode("utf-8").strip()})


@app.get("/fx")
def fx():
    if not FX_ENDPOINT:
        return jsonify({"error": "no upstream rate service configured"}), 503
    upstream = requests.get(FX_ENDPOINT, verify=False)
    return jsonify({"source": FX_ENDPOINT, "rate": upstream.json()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5017")), debug=True)
