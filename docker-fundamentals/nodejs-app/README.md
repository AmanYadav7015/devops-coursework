# Node.js Hello World

**Assignment requirements** (verbatim from `DevOps Homework.docx`):

> - Create a separate folder: `nodejs-app`
> - Add the application code.
> - Create a Dockerfile.
> - Build the Docker image.
> - Run the application using Docker.
> - Verify that Hello World is displayed on a webpage.

*Built and run on macOS with Docker Desktop, from `docker-fundamentals/nodejs-app/`.*

[← Back to Docker Fundamentals](../README.md)

---

## What's here

- `server.js` — a plain Node.js HTTP server using only the built-in `http` module.
  No `package.json`, no `npm install`, no framework — this keeps the build fast and
  fully offline-safe. It returns a small HTML page with "Hello World" and the
  container's hostname.
- `Dockerfile` — builds a `node:22-alpine` image that runs `server.js`.

## Dockerfile, line by line

```dockerfile
FROM node:22-alpine
WORKDIR /app
COPY server.js .
EXPOSE 3000
CMD ["node", "server.js"]
```

| Line | What it does |
|---|---|
| `FROM node:22-alpine` | Base image: Node.js 22 LTS on Alpine Linux. Alpine keeps the image small (~58MB layer content vs. ~350MB+ for `node:22` on Debian). |
| `WORKDIR /app` | Creates `/app` inside the container and makes it the current directory for all following instructions (`COPY`, `CMD`, etc.). |
| `COPY server.js .` | Copies `server.js` from the build context (this folder) into `/app` in the image. |
| `EXPOSE 3000` | Documents that the container listens on port 3000. Purely informational — it does not publish the port; `-p` on `docker run` does that. |
| `CMD ["node", "server.js"]` | The default command executed when the container starts: run the server with plain `node`. |

## Build & run

```bash
docker build -t df-nodejs:1.0 .
docker run -d --name df-nodejs -p 18081:3000 df-nodejs:1.0
curl -s http://localhost:18081
```

## What actually happened

The build was instant (no dependency install) and produced an image with **228MB disk
usage / 58.1MB content size** (`docker images`). The container started immediately and
`curl -s http://localhost:18081` returned a page containing:

```html
<title>Node.js Hello World</title>
...
<h1>Hello World</h1>
```

`curl -I` returned `HTTP/1.1 200 OK`. No issues were hit building or running this one —
it's the simplest app in the set because it has zero dependencies to install.
