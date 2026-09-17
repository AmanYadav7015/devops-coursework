import os

from flask import Flask, jsonify
from waitress import serve

app = Flask(__name__)


@app.get("/")
def index():
    return "Hello World from Python multi-stage build", 200, {"Content-Type": "text/plain"}


@app.get("/health")
def health():
    return jsonify(status="ok", runtime="python")


if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
