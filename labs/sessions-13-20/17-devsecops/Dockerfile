FROM python:3.13-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5017

WORKDIR /srv

COPY --from=builder /build/wheels /tmp/wheels
COPY requirements.txt .

RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels -r requirements.txt \
 && rm -rf /tmp/wheels \
 && rm -rf /usr/local/lib/python3.*/site-packages/pip \
           /usr/local/lib/python3.*/site-packages/pip-*.dist-info \
           /usr/local/lib/python3.*/site-packages/setuptools \
           /usr/local/lib/python3.*/site-packages/setuptools-*.dist-info \
           /usr/local/lib/python3.*/site-packages/pkg_resources \
           /usr/local/lib/python3.*/site-packages/wheel \
           /usr/local/lib/python3.*/site-packages/wheel-*.dist-info \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.* \
           /usr/local/bin/wheel \
 && find /usr/local -name '__pycache__' -type d -prune -exec rm -rf {} +

COPY app ./app

RUN groupadd --gid 10001 claims \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin claims \
 && chown -R claims:claims /srv

USER 10001

EXPOSE 5017

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5017/health', timeout=2).status == 200 else 1)"]

CMD ["gunicorn", "--bind", "0.0.0.0:5017", "--workers", "2", "--access-logfile", "-", "app.server:app"]
