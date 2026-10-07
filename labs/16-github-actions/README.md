# Session 16 — CI/CD with GitHub Actions

A small Flask service (`yatri-fare-api`) that exists so a real CI/CD pipeline has something real
to lint, test, package, containerise and deploy.

The pipeline lives at [`.github/workflows/session16-cicd.yml`](../../.github/workflows/session16-cicd.yml)
and runs on this branch (`session-16-ci`) on every push that touches this directory, and on manual
`workflow_dispatch`.

## Layout

```text
labs/16-github-actions/
├── app/
│   ├── __init__.py          service name constant
│   ├── fare.py              pure fare-pricing rules, no framework
│   └── server.py            Flask HTTP surface: /health, /version, /fare
├── tests/
│   ├── test_fare.py         15 tests over the pricing rules
│   └── test_server.py       5 tests over the HTTP endpoints
├── Dockerfile               multi-stage, wheels in stage 1, non-root runtime
├── build.sh                 produces dist/ with app, Dockerfile and build-info.txt
├── requirements.txt         runtime deps (Flask, gunicorn)
├── requirements-dev.txt     adds pytest, pytest-cov, flake8
└── setup.cfg                flake8 and pytest configuration
```

## Pipeline shape

```text
             push / workflow_dispatch
                       │
          ┌────────────┴────────────┐
          │                         │
      CI / Lint          CI / Test (py3.11, 3.12, 3.13)
          │                         │
          └────────────┬────────────┘
                       │
                 CI / Package                 (downloads the 3 test reports,
                       │                       uploads yatri-fare-api-package)
                       │
               CD / Build image               (downloads the package,
                       │                       builds and exports the image)
                       │
            CD / Deploy to staging            (loads the image, runs it,
                       │                       smoke tests it with real HTTP)
                       │
                Pipeline summary
```

## Run it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
.venv/bin/flake8 .
APP_VERSION=1.0.0-local ./build.sh dist
docker build -t yatri-fare-api:local dist
docker run --rm -p 8080:8080 yatri-fare-api:local
curl -s localhost:8080/health
```

## Secrets

The CD job reads three repository secrets. They hold placeholder values and are never printed:

| Secret | Purpose |
| --- | --- |
| `SESSION16_REGISTRY_USERNAME` | identity the release is published under |
| `SESSION16_REGISTRY_TOKEN` | registry credential |
| `SESSION16_DEPLOY_WEBHOOK` | endpoint notified once the release is live |

The full walkthrough with captured pipeline output is kept with the coursework notes for this session.
