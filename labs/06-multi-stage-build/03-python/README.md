# 03-python — Python multi-stage build

Flask app served by Waitress on **container port 8080**, published on host port 8092. Returns
`Hello World from Python multi-stage build` and exposes a `/health` JSON endpoint.

## The multi-stage pattern: build wheels, then install them on a slim runtime

```text
FROM python:3.12 AS builder
WORKDIR /build
COPY requirements.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
    && rm -rf /wheels
COPY app.py ./
EXPOSE 8080
CMD ["python", "app.py"]
```

This is the standard Python answer to a problem that bites everyone eventually: some packages need a C
toolchain to build, but nothing needs a C toolchain to *run*. The `builder` stage uses the full
`python:3.12` image, which ships `gcc` and the CPython headers, and turns `requirements.txt` into a
directory of prebuilt `.whl` files. The runtime stage uses `python:3.12-slim`, which has no compiler at
all, and installs from those wheels with `--no-index` so pip never touches the network again. The
result is a reproducible, offline, compiler-free runtime image.

Verification that the compiler really is gone:

```bash
docker run --rm hw06-python:multi  sh -c 'which gcc || echo "gcc: not found"'
docker run --rm hw06-python:single sh -c 'which gcc'
```

```text
gcc: not found
/usr/bin/gcc
```

## Build, run, verify

```bash
docker build -t hw06-python:multi  -f Dockerfile .
docker build -t hw06-python:single -f Dockerfile.single-stage .
docker run -d --name hw06-python -p 8092:8080 hw06-python:multi
curl -s http://localhost:8092/
curl -s http://localhost:8092/health
```

```text
Hello World from Python multi-stage build
{"runtime":"python","status":"ok"}
```

## Measured size

| Build | Base image | Disk usage | Pull size |
|---|---|---|---|
| `hw06-python:single` | `python:3.12` | 1.62 GB | 405 MB |
| `hw06-python:multi` | `python:3.12-slim` | 223 MB | 49.2 MB |

**Saving: 1.40 GB on disk (−86.2%), 356 MB per pull (−87.9%).**
