# Nginx Hello World

**Assignment requirements** (verbatim from `DevOps Homework.docx`):

> - Create a separate folder: `nginx-app`
> - Add the application code.
> - Create a Dockerfile.
> - Build the Docker image.
> - Run the application using Docker.
> - Verify that Hello World is displayed on a webpage.

*Built and run on macOS with Docker Desktop, from `docker-fundamentals/nginx-app/`.*

[← Back to Docker Fundamentals](../README.md)

---

## What's here

- `index.html` — a static Hello World page (different styling from `Apache-app`).
- `default.conf` — a **custom nginx server block**, deliberately different from
  the base image default and from `Apache-app`: it adds a custom
  `X-Served-By` response header and a dedicated `/health` endpoint that returns
  a plain-text `ok`.
- `Dockerfile` — builds an `nginx:alpine` image with our config and page.

## Dockerfile, line by line

```dockerfile
FROM nginx:alpine
COPY default.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

| Line | What it does |
|---|---|
| `FROM nginx:alpine` | Official Nginx image on Alpine Linux — small footprint. |
| `COPY default.conf /etc/nginx/conf.d/default.conf` | Replaces the default server block with our own (custom header + `/health` route), so this app isn't config-identical to `Apache-app` or a bare nginx image. |
| `COPY index.html /usr/share/nginx/html/index.html` | Replaces Nginx's default welcome page with our Hello World page. `/usr/share/nginx/html` is this image's default web root. |
| `EXPOSE 80` | Documents the listening port. |
| `CMD ["nginx", "-g", "daemon off;"]` | Runs Nginx in the foreground (the base image already sets this `CMD`; restated for clarity). |

## Build & run

```bash
docker build -t df-nginx:1.0 .
docker run -d --name df-nginx -p 18086:80 df-nginx:1.0
curl -s http://localhost:18086
curl -s http://localhost:18086/health
```

## What actually happened

Build and run were immediate. Final image: **92.8MB disk usage / 26.2MB content
size**.

`curl -s http://localhost:18086` returned HTML containing `<h1>Hello World</h1>`.
`curl -I` returned:

```
HTTP/1.1 200 OK
Server: nginx/1.31.4
Content-Type: text/html
X-Served-By: nginx-app-docker-homework
```

The `X-Served-By` header confirms the custom `default.conf` is actually the one
in effect (not just the base image's default config).
