# Python Hello World

A Flask app that answers `GET /` with `Hello World from Python`. It listens on port 5000 inside the
container; on macOS the host port is 5001 because AirPlay Receiver already owns host port 5000.

## Build

```bash
cd homework/05-docker-hello-world/python-app
docker build -t hw05-python .
```

## Run

```bash
docker run -d --name hw05-python -p 5001:5000 hw05-python
docker ps --filter name=hw05-python
```

## Verify

```bash
curl http://localhost:5001
```

```text
<h1>Hello World from Python</h1>
```

Or open <http://localhost:5001> in a browser.

## Clean up

```bash
docker rm -f hw05-python
```
