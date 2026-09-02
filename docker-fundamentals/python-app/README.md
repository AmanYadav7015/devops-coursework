# Python Hello World

**Assignment requirements** (verbatim from `DevOps Homework.docx`):

> - Create a separate folder: `python-app`
> - Add the application code.
> - Create a Dockerfile.
> - Build the Docker image.
> - Run the application using Docker.
> - Verify that Hello World is displayed on a webpage.

*Built and run on macOS with Docker Desktop, from `docker-fundamentals/python-app/`.*

[← Back to Docker Fundamentals](../README.md)

---

## What's here

- `app.py` — a plain Python app using only the standard library's
  `http.server.HTTPServer` / `BaseHTTPRequestHandler`. No Flask, no `pip install`,
  no `requirements.txt` — this avoids a slow/network-dependent build and keeps the
  image small. It serves a small HTML page with "Hello World" and the container's
  hostname.
- `Dockerfile` — builds a `python:3.12-alpine` image that runs `app.py`.

## Dockerfile, line by line

```dockerfile
FROM python:3.12-alpine
WORKDIR /app
COPY app.py .
EXPOSE 5000
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
```

| Line | What it does |
|---|---|
| `FROM python:3.12-alpine` | Base image: Python 3.12 on Alpine Linux — small footprint compared to `python:3.12` (Debian-based). |
| `WORKDIR /app` | Sets `/app` as the working directory for subsequent instructions. |
| `COPY app.py .` | Copies the stdlib-only app into the image. No dependency install step needed. |
| `EXPOSE 5000` | Documents the port the app listens on (informational only). |
| `ENV PYTHONUNBUFFERED=1` | See "What actually happened" below — without this, log output never reaches `docker logs`. |
| `CMD ["python", "app.py"]` | Starts the server. |

## Build & run

```bash
docker build -t df-python:1.0 .
docker run -d --name df-python -p 18082:5000 df-python:1.0
curl -s http://localhost:18082
```

## What actually happened

The build was fast — no `pip install` step, so it's as offline-safe as the Node.js
app. Final image: **87.8MB disk usage / 21.4MB content size**, the smallest of all
six images (smaller than Node.js because Alpine Python's runtime is lighter than
Alpine Node's, and there's no extra tooling layered on).

`curl -s http://localhost:18082` returned HTML containing `<h1>Hello World</h1>`.
`curl -I` (a HEAD request) returned `HTTP/1.0 501 Unsupported method ('HEAD')` —
that's expected and not a bug: `BaseHTTPRequestHandler` only dispatches methods for
which you've defined a handler, and this app only defines `do_GET`. A production
app would add a `do_HEAD` handler; for a "serve one Hello World page" homework app
it wasn't needed since the actual page loads fine over `GET`.

**Real bug found and fixed:** while testing `docker logs df-python` for the
inspection transcript, the log was completely empty even after several `curl`
requests had been served successfully. Root cause: Python buffers stdout when it
isn't attached to a TTY (always true for a container's main process), so
`print()` / the handler's `log_message()` output sat in a buffer instead of being
flushed to the container's stdout stream that `docker logs` reads. Adding
`ENV PYTHONUNBUFFERED=1` to the Dockerfile and rebuilding fixed it — logs then
appeared immediately after each request. See `transcripts/docker-c.txt` for the
before/after.
