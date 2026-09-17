# Apache Hello World

A static page served by the Apache HTTP Server (`httpd`). Apache's document root inside the official
image is `/usr/local/apache2/htdocs`, so the Dockerfile only has to copy `index.html` there.

## Build

```bash
cd homework/05-docker-hello-world/apache-app
docker build -t hw05-apache .
```

## Run

```bash
docker run -d --name hw05-apache -p 8081:80 hw05-apache
docker ps --filter name=hw05-apache
```

## Verify

```bash
curl http://localhost:8081
```

```text
<h1>Hello World from Apache</h1>
```

Or open <http://localhost:8081> in a browser.

## Clean up

```bash
docker rm -f hw05-apache
```
