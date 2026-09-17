# Nginx Hello World

A static page served by Nginx. The Alpine variant of the official image keeps the result around 100 MB.
Nginx serves `/usr/share/nginx/html` by default, so the Dockerfile only copies `index.html` there.

## Build

```bash
cd homework/05-docker-hello-world/nginx-app
docker build -t hw05-nginx .
```

## Run

```bash
docker run -d --name hw05-nginx -p 8083:80 hw05-nginx
docker ps --filter name=hw05-nginx
```

## Verify

```bash
curl http://localhost:8083
```

```text
<h1>Hello World from Nginx</h1>
```

Or open <http://localhost:8083> in a browser.

## Clean up

```bash
docker rm -f hw05-nginx
```
