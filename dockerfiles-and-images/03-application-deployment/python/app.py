# Python + Flask deployment demo (Task 3: Docker Application Deployment).
# Exposes a small JSON API (/api/info) and an HTML page (/), and reports
# the CPython runtime version and the Flask framework version.
import datetime
import platform
import socket

import flask
from flask import Flask, jsonify

app = Flask(__name__)
PORT = 5000


@app.route("/api/info")
def info():
    return jsonify(
        app="ms-deploy-python",
        language="Python",
        runtime=f"CPython {platform.python_version()}",
        framework=f"Flask {flask.__version__}",
        hostname=socket.gethostname(),
        platform=f"{platform.system()} {platform.machine()}",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


@app.route("/")
def index():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Python Deployment Demo</title>
  <style>
    body {{ font-family: sans-serif; background:#0b132b; color:#e0e6ed; text-align:center; padding-top:70px; }}
    h1 {{ font-size: 2.6em; color:#f9c74f; }}
    p {{ color:#8892a6; }}
    code {{ background:#1c2541; padding:2px 8px; border-radius:4px; }}
  </style>
</head>
<body>
  <h1>Python Deployment Demo</h1>
  <p>Runtime: <strong>CPython {platform.python_version()}</strong> &middot; Framework: <strong>Flask {flask.__version__}</strong></p>
  <p>JSON API: <code>GET /api/info</code></p>
  <p>Hostname: {socket.gethostname()}</p>
</body>
</html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
