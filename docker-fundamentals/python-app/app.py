# Plain Python stdlib HTTP server - no pip install required (fast, offline-safe build).
from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
import os

PORT = int(os.environ.get("PORT", 5000))

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Python Hello World</title>
  <style>
    body {{ font-family: sans-serif; background:#0b132b; color:#e0e6ed; text-align:center; padding-top:80px; }}
    h1 {{ font-size: 3em; color:#f9c74f; }}
    p {{ color:#8892a6; }}
  </style>
</head>
<body>
  <h1>Hello World</h1>
  <p>Served by a plain <strong>Python</strong> http.server (python:3.12-alpine)</p>
  <p>Hostname: {socket.gethostname()}</p>
</body>
</html>"""


class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Keep container logs concise but still show requests
        print("%s - %s" % (self.address_string(), format % args))


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), HelloHandler)
    print(f"Python Hello World server listening on port {PORT}")
    server.serve_forever()
