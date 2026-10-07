FROM python:3.11-slim-bullseye

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PORT=5017
EXPOSE 5017

CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:5017", "--workers", "2", "app.server:app"]
