# Assignment 6 — Dockerfiles & Images: Multi-Stage Build

**Name:** Aman Yadav
**Roll Number:** 24bcs10183
**Year:** 2nd Year
**Batch:** A
**Assignment:** Docker Multi-Stage Build
**Environment:** macOS (Darwin arm64), Docker Desktop, Docker Engine 29.4.1

---

## Task 1 — Multi-stage image built, container running, app accessed on port 8080

### The multi-stage Dockerfile

```bash
cat 01-main-app/Dockerfile
```

```text
FROM node:24-alpine AS builder
WORKDIR /build
COPY package.json ./
RUN npm install --omit=dev
COPY server.js ./

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /build/node_modules ./node_modules
COPY --from=builder /build/package.json ./package.json
COPY --from=builder /build/server.js ./server.js
EXPOSE 8080
CMD ["node", "server.js"]
```

### Build and run

```bash
docker build -t hw06-main-app:multi -f Dockerfile .
docker run -d --name hw06-main-app -p 8080:8080 hw06-main-app:multi
```

### Output of the application running

Container startup log:

```bash
docker logs hw06-main-app
```

```text
main-app listening on port 8080
```

Response body:

```bash
curl -s http://localhost:8080/
```

```text
Hello World from Docker multi-stage build
```

Full HTTP response:

```bash
curl -s -i http://localhost:8080/
```

```text
HTTP/1.1 200 OK
X-Powered-By: Express
Content-Type: text/plain; charset=utf-8
Content-Length: 41
ETag: W/"29-IhsxEoza/NIQ8BuEKoQlCDzwaRQ"
Date: Thu, 17 Sep 2026 16:16:05 GMT
Connection: keep-alive
Keep-Alive: timeout=5

Hello World from Docker multi-stage build
```

Exact-match verification of the required string:

```bash
curl -s http://localhost:8080/ | grep -c '^Hello World from Docker multi-stage build$'
```

```text
1
```

The count of `1` on an anchored whole-line pattern confirms the body is exactly
`Hello World from Docker multi-stage build`.

### Output of `docker ps` showing port 8080

```bash
docker ps --filter 'name=hw06-main-app'
```

```text
CONTAINER ID   IMAGE                 COMMAND                  CREATED          STATUS          PORTS                                         NAMES
5be986701071   hw06-main-app:multi   "docker-entrypoint.s…"   22 seconds ago   Up 21 seconds   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp   hw06-main-app
```

The `PORTS` column shows `->8080/tcp`: the container port is **8080**.

---

## Task 3 — Three application types deployed with Docker

All four containers running simultaneously, each built from its own multi-stage Dockerfile:

```bash
docker ps --filter 'name=hw06-'
```

```text
CONTAINER ID   IMAGE                 COMMAND                  CREATED          STATUS          PORTS                                         NAMES
9acbfba8ad90   hw06-java:multi       "/__cacert_entrypoin…"   4 seconds ago    Up 4 seconds    0.0.0.0:8093->8080/tcp, [::]:8093->8080/tcp   hw06-java
1fd79ec4aa62   hw06-python:multi     "python app.py"          4 seconds ago    Up 4 seconds    0.0.0.0:8092->8080/tcp, [::]:8092->8080/tcp   hw06-python
9f8fce332686   hw06-node:multi       "docker-entrypoint.s…"   4 seconds ago    Up 4 seconds    0.0.0.0:8091->8080/tcp, [::]:8091->8080/tcp   hw06-node
5be986701071   hw06-main-app:multi   "docker-entrypoint.s…"   22 seconds ago   Up 21 seconds   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp   hw06-main-app
fea7d979ee76   hw06-java:multi       "/__cacert_entrypoin…"   54 seconds ago   Up 54 seconds   0.0.0.0:8093->8080/tcp, [::]:8093->8080/tcp   hw06-java
90f546003c01   hw06-python:multi     "python app.py"          54 seconds ago   Up 54 seconds   0.0.0.0:8092->8080/tcp, [::]:8092->8080/tcp   hw06-python
e8c0649fa460   hw06-node:multi       "docker-entrypoint.s…"   55 seconds ago   Up 54 seconds   0.0.0.0:8091->8080/tcp, [::]:8091->8080/tcp   hw06-node
```

```bash
curl -s http://localhost:8091/
curl -s http://localhost:8092/
curl -s http://localhost:8093/
```

```text
Hello World from Node.js multi-stage build
Hello World from Python multi-stage build
Hello World from Java multi-stage build
```

---

## Measured result: single-stage vs multi-stage

```bash
docker images --filter=reference='hw06-*'
```

```text
IMAGE                  ID             DISK USAGE   CONTENT SIZE   EXTRA
hw06-java:multi        20606c6851c6        286MB         73.4MB   U
hw06-java:single       a1abacedc830        744MB          221MB
hw06-main-app:multi    5ee9a160a69f        237MB         59.7MB   U
hw06-main-app:single   971c0e1b2b8f       1.88GB          445MB
hw06-node:multi        de13fed72af6        237MB         59.7MB   U
hw06-node:single       1eb8216b4e2e       1.91GB          454MB
hw06-python:multi      aaab7c3a0c13        223MB         49.2MB   U
hw06-python:single     ce1a400a1491       1.62GB          405MB
```

| Application | Single-stage | Multi-stage | Saved |
|---|---|---|---|
| Main app (Node.js) | 1.88 GB | 237 MB | 1.64 GB (−87.4%) |
| Node.js app | 1.91 GB | 237 MB | 1.67 GB (−87.6%) |
| Python app | 1.62 GB | 223 MB | 1.40 GB (−86.2%) |
| Java app | 744 MB | 286 MB | 458 MB (−61.6%) |

Both builds of each application serve identical responses. The difference is only in what gets shipped:
the multi-stage images contain no compilers, no package-manager caches, no dev dependencies and no
source code.

Full lab walkthrough with all commands, output and explanation: [`README.md`](README.md).
