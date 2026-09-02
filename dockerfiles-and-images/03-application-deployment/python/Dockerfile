# Multi-stage build for the Python deployment demo.
#
# Stage 1 "builder": creates a virtualenv and pip-installs Flask into it
# (needs pip's build/download machinery and any wheel-building tools).
# Stage 2 copies only the finished virtualenv into a clean runtime image,
# so pip itself and its cache never reach the image that actually runs.

# ---- Stage 1: builder ----
FROM python:3.12-alpine AS builder
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: runtime ----
FROM python:3.12-alpine
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY app.py .

EXPOSE 5000
RUN adduser -D appuser
USER appuser

CMD ["python", "app.py"]
