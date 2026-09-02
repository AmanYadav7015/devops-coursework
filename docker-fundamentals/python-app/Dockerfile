# Small official Python image on Alpine Linux (~50MB base)
FROM python:3.12-alpine

# Set working directory inside the container
WORKDIR /app

# Copy application source. Uses only the Python standard library
# (http.server) so there is no pip install / requirements.txt needed -
# keeps the build fast and works completely offline.
COPY app.py .

# Document the port the app listens on
EXPOSE 5000

# Python buffers stdout when it isn't attached to a TTY (which is always the
# case for a container's main process), so print()/log_message() output would
# sit in a buffer and never show up in `docker logs` until the buffer filled
# or the process exited. PYTHONUNBUFFERED=1 forces unbuffered stdout/stderr
# so log lines appear immediately - discovered while testing `docker logs`.
ENV PYTHONUNBUFFERED=1

# Start the server
CMD ["python", "app.py"]
