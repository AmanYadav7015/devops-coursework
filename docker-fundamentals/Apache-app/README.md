# Apache Hello World

**Assignment requirements** (verbatim from `DevOps Homework.docx`):

> - Create a separate folder: `Apache-app`
> - Add the application code.
> - Create a Dockerfile.
> - Build the Docker image.
> - Run the application using Docker.
> - Verify that Hello World is displayed on a webpage.

*Built and run on macOS with Docker Desktop, from `docker-fundamentals/Apache-app/`.*

[← Back to Docker Fundamentals](../README.md)

---

## What's here

- `index.html` — a static Hello World page.
- `Dockerfile` — builds an `httpd:2.4-alpine` image with our page replacing
  Apache's default "It works!" page.

## Dockerfile, line by line

```dockerfile
FROM httpd:2.4-alpine
COPY index.html /usr/local/apache2/htdocs/index.html
EXPOSE 80
CMD ["httpd-foreground"]
```

| Line | What it does |
|---|---|
| `FROM httpd:2.4-alpine` | Official Apache HTTP Server 2.4 image on Alpine Linux — much smaller than the Debian-based `httpd:2.4` tag. |
| `COPY index.html /usr/local/apache2/htdocs/index.html` | Overwrites Apache's default document root page with our own. `htdocs/` is Apache's default `DocumentRoot` in this image. |
| `EXPOSE 80` | Documents that Apache listens on port 80 (its default). |
| `CMD ["httpd-foreground"]` | Runs Apache in the foreground so the container keeps running (the base image already defines this `CMD`; it's restated here for clarity/self-documentation). |

## Build & run

```bash
docker build -t df-apache:1.0 .
docker run -d --name df-apache -p 18084:80 df-apache:1.0
curl -s http://localhost:18084
```

## What actually happened

Build and run were both immediate — no compilation, no dependency install, just a
static file copy. Final image: **105MB disk usage / 21.1MB content size**.

`curl -s http://localhost:18084` returned HTML containing `<h1>Hello World</h1>`,
and `curl -I` returned:

```
HTTP/1.1 200 OK
Server: Apache/2.4.68 (Unix)
Content-Type: text/html
```

confirming the real Apache server (not a substitute) is what's answering requests.
