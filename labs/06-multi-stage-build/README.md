# Assignment 6 — Dockerfiles & Images: Multi-Stage Build

This lab builds one application **twice** — once with a naive single-stage Dockerfile and once with a
multi-stage Dockerfile — so the size saving is a **measured number**, not a claim. It then repeats the
exercise for three different application types (Node.js, Python, Java) and runs all of them at the same time.

Everything in this file is real terminal output captured while running the lab on macOS (Darwin arm64)
with Docker Desktop.

## Folder layout

```bash
cd homework/06-multi-stage-build
ls -1
```

```text
01-main-app
02-nodejs
03-python
04-java
README.md
submission.md
```

Every app folder contains the application source, a `Dockerfile` (multi-stage) and a
`Dockerfile.single-stage` (the naive version we are comparing against).

## A note on the host port

The assignment asks for the app on port **8080**, and that is exactly where it runs: the container
listens on 8080 via `EXPOSE 8080`, and the publish is `-p 8080:8080`, so `docker ps` shows
`0.0.0.0:8080->8080/tcp`.

If host port 8080 is already allocated on your machine, Docker refuses the run with this error:

```text
docker: Error response from daemon: failed to set up container networking: driver failed programming
external connectivity on endpoint hw06-main-app: Bind for 0.0.0.0:8080 failed: port is already allocated
```

Free the port, or publish on another host port such as `-p 8090:8080`. The container-side port is
always 8080 regardless of which host port you pick.

---

## Part 1 — The multi-stage application

### The application

```bash
cat 01-main-app/server.js
```

```text
const express = require("express");

const app = express();
const PORT = process.env.PORT || 8080;

app.get("/", (req, res) => {
  res.type("text/plain").send("Hello World from Docker multi-stage build");
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`main-app listening on port ${PORT}`);
});
```

```bash
cat 01-main-app/package.json
```

```text
{
  "name": "hw06-main-app",
  "version": "1.0.0",
  "private": true,
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^5.1.0"
  },
  "devDependencies": {
    "eslint": "^9.36.0",
    "jest": "^30.1.3"
  }
}
```

The `devDependencies` are there on purpose. They are what a real project carries, and they are exactly
the kind of thing that has no business being inside a production image. The multi-stage build is going
to leave them behind.

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

Two `FROM` lines means two stages. The first stage, named `builder`, does the work: it installs the
dependency tree. The second stage starts from a **fresh, empty base image** and pulls across only the
finished artifacts with `COPY --from=builder`. Nothing else from the builder stage survives into the
final image — not the npm cache, not the intermediate layers, not anything you did and then deleted.

### The single-stage Dockerfile we are comparing against

```bash
cat 01-main-app/Dockerfile.single-stage
```

```text
FROM node:24
WORKDIR /app
COPY package.json ./
RUN npm install
COPY server.js ./
EXPOSE 8080
CMD ["node", "server.js"]
```

This is how most people write their first Dockerfile: grab the default (full) language image, install
everything, copy the source in, run it. It works perfectly well. It is also enormous, and the rest of
this lab shows exactly how enormous.

### Build both images

```bash
cd 01-main-app
docker build -t hw06-main-app:multi -f Dockerfile .
docker build -t hw06-main-app:single -f Dockerfile.single-stage .
```

Output of the multi-stage build (second run, so the layers are cached):

```text
#1 [internal] load build definition from Dockerfile
#1 DONE 0.0s
#2 [internal] load metadata for docker.io/library/node:24-alpine
#2 DONE 1.9s
#3 [internal] load .dockerignore
#3 DONE 0.0s
#4 [builder 1/5] FROM docker.io/library/node:24-alpine@sha256:50c8e8ca1d27439048670df5883f32d57cf81cff6233222c893fd0d9884cbd81
#4 DONE 0.0s
#5 [internal] load build context
#5 DONE 0.0s
#6 [builder 3/5] COPY package.json ./
#6 CACHED
#7 [builder 4/5] RUN npm install --omit=dev
#7 CACHED
#8 [runtime 4/5] COPY --from=builder /build/package.json ./package.json
#8 CACHED
#9 [runtime 2/5] WORKDIR /app
#9 CACHED
#10 [builder 2/5] WORKDIR /build
#10 CACHED
#11 [builder 5/5] COPY server.js ./
#11 CACHED
#12 [runtime 3/5] COPY --from=builder /build/node_modules ./node_modules
#12 CACHED
#13 [runtime 5/5] COPY --from=builder /build/server.js ./server.js
#13 CACHED
#14 exporting to image
#14 naming to docker.io/library/hw06-main-app:multi done
#14 DONE 0.0s
```

Notice the step labels: BuildKit tells you which stage each step belongs to — `[builder 4/5]` versus
`[runtime 3/5]`. That is the clearest signal that two separate images are being assembled.

### Run the container

```bash
docker run -d --name hw06-main-app -p 8080:8080 hw06-main-app:multi
docker logs hw06-main-app
```

```text
main-app listening on port 8080
```

The app reports **port 8080** — that is the port inside the container, which is what the assignment asks for.

### Access the app and verify the required string

```bash
curl -s http://localhost:8080/
```

```text
Hello World from Docker multi-stage build
```

With headers, to show it is a real HTTP 200:

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

And an exact, whole-line match against the required string:

```bash
curl -s http://localhost:8080/ | grep -c '^Hello World from Docker multi-stage build$'
```

```text
1
```

`grep -c` with `^...$` anchors returns `1`, so the response body is the required string exactly, with
nothing before or after it.

### Verify with `docker ps`

```bash
docker ps --filter 'name=hw06-main-app'
```

```text
CONTAINER ID   IMAGE                 COMMAND                  CREATED          STATUS          PORTS                                         NAMES
5be986701071   hw06-main-app:multi   "docker-entrypoint.s…"   22 seconds ago   Up 21 seconds   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp   hw06-main-app
```

The `PORTS` column reads `0.0.0.0:8080->8080/tcp`. Read it right to left: the container is serving on
**8080**, and Docker is forwarding host port 8080 into it.

The single-stage image runs the same application and returns the same string — the difference is purely
in what got shipped:

```bash
docker run -d --name hw06-main-app-single hw06-main-app:single
docker exec hw06-main-app-single node -e "fetch('http://localhost:8080/').then(r=>r.text()).then(t=>console.log(t))"
```

```text
Hello World from Docker multi-stage build
```

---

## Part 2 — The measured size saving

This is the whole point of the assignment. Same source code, same output, two build strategies.

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

Docker 29 reports two numbers. **DISK USAGE** is what the image occupies on this machine once
unpacked. **CONTENT SIZE** is the compressed size that travels over the network when someone pulls
the image — that is the number your CI runners and your Kubernetes nodes actually pay for.

### Size comparison table

| Application | Single-stage disk | Multi-stage disk | Disk saved | Single-stage pull | Multi-stage pull | Pull saved |
|---|---|---|---|---|---|---|
| Main app (Node.js, Task 1) | 1.88 GB | 237 MB | **1.64 GB, −87.4%** | 445 MB | 59.7 MB | −86.6% |
| Node.js app (Task 3) | 1.91 GB | 237 MB | **1.67 GB, −87.6%** | 454 MB | 59.7 MB | −86.8% |
| Python app (Task 3) | 1.62 GB | 223 MB | **1.40 GB, −86.2%** | 405 MB | 49.2 MB | −87.9% |
| Java app (Task 3) | 744 MB | 286 MB | **458 MB, −61.6%** | 221 MB | 73.4 MB | −66.8% |

The Java saving is smaller in percentage terms only because a JRE is genuinely large — you cannot run
Java without one. The saving is still 458 MB per image, on every pull, on every node.

### `docker history` — where the bytes went

```bash
docker history hw06-main-app:multi
```

```text
IMAGE          CREATED         CREATED BY                                      SIZE      COMMENT
5ee9a160a69f   4 minutes ago   CMD ["node" "server.js"]                        0B        buildkit.dockerfile.v0
<missing>      4 minutes ago   EXPOSE [8080/tcp]                               0B        buildkit.dockerfile.v0
<missing>      4 minutes ago   COPY /build/server.js ./server.js # buildkit    12.3kB    buildkit.dockerfile.v0
<missing>      4 minutes ago   COPY /build/package.json ./package.json # bu…   12.3kB    buildkit.dockerfile.v0
<missing>      4 minutes ago   COPY /build/node_modules ./node_modules # bu…   4.54MB    buildkit.dockerfile.v0
<missing>      4 minutes ago   ENV NODE_ENV=production                         0B        buildkit.dockerfile.v0
<missing>      6 minutes ago   WORKDIR /app                                    8.19kB    buildkit.dockerfile.v0
<missing>      7 days ago      CMD ["node"]                                    0B        buildkit.dockerfile.v0
<missing>      7 days ago      ENTRYPOINT ["docker-entrypoint.sh"]             0B        buildkit.dockerfile.v0
<missing>      7 days ago      COPY docker-entrypoint.sh /usr/local/bin/ # …   20.5kB    buildkit.dockerfile.v0
<missing>      7 days ago      RUN /bin/sh -c apk add --no-cache --virtual …   5.48MB    buildkit.dockerfile.v0
<missing>      7 days ago      ENV YARN_VERSION=1.22.22                        0B        buildkit.dockerfile.v0
<missing>      7 days ago      RUN /bin/sh -c addgroup -g 1000 node     && …   158MB     buildkit.dockerfile.v0
<missing>      7 days ago      ENV NODE_VERSION=24.21.0                        0B        buildkit.dockerfile.v0
<missing>      3 months ago    CMD ["/bin/sh"]                                 0B        buildkit.dockerfile.v0
<missing>      3 months ago    ADD alpine-minirootfs-3.24.1-aarch64.tar.gz …   9.31MB    buildkit.dockerfile.v0
```

Read this from the bottom up. The Alpine root filesystem is 9.31 MB, the Node runtime is 158 MB, and
**everything this lab added is 4.57 MB**: the production `node_modules`, the manifest and the one source
file. There is no layer here from the builder stage. The `npm install` step does not appear at all —
it happened in a stage that was thrown away.

```bash
docker history hw06-main-app:single
```

```text
IMAGE          CREATED         CREATED BY                                      SIZE      COMMENT
971c0e1b2b8f   2 minutes ago   CMD ["node" "server.js"]                        0B        buildkit.dockerfile.v0
<missing>      2 minutes ago   EXPOSE [8080/tcp]                               0B        buildkit.dockerfile.v0
<missing>      2 minutes ago   COPY server.js ./ # buildkit                    12.3kB    buildkit.dockerfile.v0
<missing>      2 minutes ago   RUN /bin/sh -c npm install # buildkit           211MB     buildkit.dockerfile.v0
<missing>      2 minutes ago   COPY package.json ./ # buildkit                 12.3kB    buildkit.dockerfile.v0
<missing>      2 minutes ago   WORKDIR /app                                    8.19kB    buildkit.dockerfile.v0
<missing>      7 days ago      CMD ["node"]                                    0B        buildkit.dockerfile.v0
<missing>      7 days ago      ENTRYPOINT ["docker-entrypoint.sh"]             0B        buildkit.dockerfile.v0
<missing>      7 days ago      COPY docker-entrypoint.sh /usr/local/bin/ # …   20.5kB    buildkit.dockerfile.v0
<missing>      7 days ago      RUN /bin/sh -c set -ex   && export GNUPGHOME…   5.41MB    buildkit.dockerfile.v0
<missing>      7 days ago      ENV YARN_VERSION=1.22.22                        0B        buildkit.dockerfile.v0
<missing>      7 days ago      RUN /bin/sh -c ARCH= && dpkgArch="$(dpkg --p…   214MB     buildkit.dockerfile.v0
<missing>      7 days ago      ENV NODE_VERSION=24.21.0                        0B        buildkit.dockerfile.v0
<missing>      7 days ago      RUN /bin/sh -c groupadd --gid 1000 node   &&…   69.6kB    buildkit.dockerfile.v0
<missing>      3 weeks ago     RUN /bin/sh -c set -ex;  apt-get update;  ap…   592MB     buildkit.dockerfile.v0
<missing>      3 weeks ago     RUN /bin/sh -c set -eux;  apt-get update;  a…   200MB     buildkit.dockerfile.v0
<missing>      3 weeks ago     RUN /bin/sh -c set -eux;  apt-get update;  a…   52.4MB    buildkit.dockerfile.v0
<missing>      3 weeks ago     # debian.sh --arch 'arm64' out/ 'bookworm' '…   155MB     debuerreotype 0.17
```

The same story, told the expensive way. `RUN npm install` is a **211 MB layer baked into the shipped
image**, because it ran in the only stage there was. Below it sit the full Debian base layers: 155 MB
of rootfs, then 52.4 MB, then 200 MB, then a 592 MB layer of build toolchain (`build-essential`, git,
compilers) that the Debian-based `node:24` image carries so you can compile native modules. None of it
is needed to run `node server.js`.

Two contributions to the saving, and it is worth being precise about them:

1. **Base image choice** — `node:24-alpine` instead of `node:24`. Worth roughly 1 GB on its own.
2. **Discarding the build stage** — the dev dependencies and npm's working files never reach the
   runtime image. Worth the difference between a 211 MB `node_modules` layer and a 4.54 MB one.

Multi-stage is what makes (1) safe. You can only pick a tiny runtime base if you have somewhere else
to do the building — and the builder stage is that somewhere else.

### Proof: what actually got left behind

Size numbers are abstract. This is concrete. Look inside the two Node images:

```bash
docker run --rm hw06-main-app:multi sh -c 'ls -1 /app; echo "--- top-level packages:"; ls -1 node_modules | grep -v "^\." | wc -l; ls -1 node_modules | grep -E "eslint|jest" || echo "eslint/jest: not present"'
```

```text
node_modules
package.json
server.js
--- top-level packages:
65
eslint/jest: not present
```

```bash
docker run --rm hw06-main-app:single sh -c 'ls -1 /app; echo "--- top-level packages:"; ls -1 node_modules | grep -v "^\." | wc -l; ls -1 node_modules | grep -E "^eslint$|^jest$"'
```

```text
node_modules
package-lock.json
package.json
server.js
--- top-level packages:
288
eslint
jest
```

65 packages versus 288. The linter and the test framework are sitting in the production image, ready to
be exploited, in the single-stage build only.

The Java pair makes the point even harder, because there the compiler itself is the difference:

```bash
docker run --rm hw06-java:multi sh -c 'ls -1 /app; echo "---"; which javac || echo "javac: not found"; which jar || echo "jar: not found"'
```

```text
app.jar
---
javac: not found
jar: not found
```

```bash
docker run --rm hw06-java:single sh -c 'ls -1 /app; echo "---"; which javac; which jar'
```

```text
app.jar
out
src
---
/opt/java/openjdk/bin/javac
/opt/java/openjdk/bin/jar
```

The multi-stage Java image contains **one file**: the jar. No `.java` source, no `.class` output
directory, no compiler. The single-stage image ships your source code and a working Java compiler to
production. Anyone who gets a shell in that container can compile and run whatever they like.

And Python:

```bash
docker run --rm hw06-python:multi sh -c 'ls -1 /app; echo "---"; which gcc || echo "gcc: not found"; ls /wheels 2>/dev/null || echo "/wheels: removed"'
```

```text
app.py
---
gcc: not found
/wheels: removed
```

```bash
docker run --rm hw06-python:single sh -c 'ls -1 /app; echo "---"; which gcc'
```

```text
app.py
requirements.txt
---
/usr/bin/gcc
```

No C compiler in the multi-stage runtime. The full `python:3.12` image ships one.

---

## Part 3 — Three application types, running together

Three languages, three genuinely different multi-stage patterns, all running at once.

| Folder | Language | Builder stage does | Runtime stage is | Host port |
|---|---|---|---|---|
| `02-nodejs` | Node.js 24 | `npm install --omit=dev` | `node:24-alpine` + `node_modules` | 8091 |
| `03-python` | Python 3.12 | `pip wheel` builds wheels | `python:3.12-slim` + installed wheels | 8092 |
| `04-java` | Java 21 | `javac` + `jar` on a JDK | `eclipse-temurin:21-jre-alpine` + the jar | 8093 |

Each folder has its own `README.md` with the full detail. The short version:

### Build and run all three

```bash
docker build -t hw06-node:multi   -f 02-nodejs/Dockerfile   02-nodejs
docker build -t hw06-python:multi -f 03-python/Dockerfile   03-python
docker build -t hw06-java:multi   -f 04-java/Dockerfile     04-java

docker run -d --name hw06-node   -p 8091:8080 hw06-node:multi
docker run -d --name hw06-python -p 8092:8080 hw06-python:multi
docker run -d --name hw06-java   -p 8093:8080 hw06-java:multi
```

### All four containers in a single `docker ps`

```bash
docker ps --filter 'name=hw06-'
```

```text
CONTAINER ID   IMAGE                 COMMAND                  CREATED          STATUS          PORTS                                         NAMES
5be986701071   hw06-main-app:multi   "docker-entrypoint.s…"   22 seconds ago   Up 21 seconds   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp   hw06-main-app
fea7d979ee76   hw06-java:multi       "/__cacert_entrypoin…"   54 seconds ago   Up 54 seconds   0.0.0.0:8093->8080/tcp, [::]:8093->8080/tcp   hw06-java
90f546003c01   hw06-python:multi     "python app.py"          54 seconds ago   Up 54 seconds   0.0.0.0:8092->8080/tcp, [::]:8092->8080/tcp   hw06-python
e8c0649fa460   hw06-node:multi       "docker-entrypoint.s…"   55 seconds ago   Up 54 seconds   0.0.0.0:8091->8080/tcp, [::]:8091->8080/tcp   hw06-node
```

Every container listens on **8080 internally**. Each gets its own host port, which is exactly why
container port mapping exists — four apps that all think they own port 8080 coexist happily.

### Curl each one

```bash
curl -s http://localhost:8080/
curl -s http://localhost:8091/
curl -s http://localhost:8092/
curl -s http://localhost:8093/
```

```text
Hello World from Docker multi-stage build
Hello World from Node.js multi-stage build
Hello World from Python multi-stage build
Hello World from Java multi-stage build
```

Health endpoints on the Node and Python apps, to show they are more than a static string:

```bash
curl -s http://localhost:8091/health
curl -s http://localhost:8092/health
```

```text
{"status":"ok","runtime":"node","version":"v24.21.0"}
{"runtime":"python","status":"ok"}
```

### Startup logs

```bash
docker logs hw06-node
docker logs hw06-java
```

```text
node app listening on port 8080
java app listening on port 8080
```

### The runtime layers of each multi-stage image

```bash
docker history hw06-python:multi --format 'table {{.CreatedBy}}\t{{.Size}}' | head -9
```

```text
CREATED BY                                      SIZE
CMD ["python" "app.py"]                         0B
EXPOSE [8080/tcp]                               0B
COPY app.py ./ # buildkit                       12.3kB
RUN /bin/sh -c pip install --no-cache-dir --…   6.33MB
COPY /wheels /wheels # buildkit                 717kB
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFER…   0B
WORKDIR /app                                    8.19kB
CMD ["python3"]                                 0B
```

```bash
docker history hw06-java:multi --format 'table {{.CreatedBy}}\t{{.Size}}' | head -8
```

```text
CREATED BY                                      SIZE
CMD ["java" "-jar" "app.jar"]                   0B
EXPOSE [8080/tcp]                               0B
COPY /build/app.jar ./app.jar # buildkit        12.3kB
WORKDIR /app                                    8.19kB
ENTRYPOINT ["/__cacert_entrypoint.sh"]          0B
COPY --chmod=755 entrypoint.sh /__cacert_ent…   12.3kB
RUN /bin/sh -c set -eux;     echo "Verifying…   12.3kB
```

The entire Java application is a single 12.3 kB layer on top of a stock JRE. The Python app is
7 MB of layers on top of a slim interpreter — and even that 717 kB `/wheels` layer is dead weight we
would delete in a stricter build, since the `rm -rf /wheels` in the same `RUN` only removes the files
from the *installed* layer, not from the layer that added them.

---

## How multi-stage builds work

A Dockerfile with more than one `FROM` is a multi-stage build. Each `FROM` starts a new, independent
image. Stages can be named with `AS <name>` and referred to later.

```text
FROM <base> AS builder      <- stage 0: has compilers, SDKs, source, caches
    ... do the expensive, messy work ...

FROM <smaller-base>         <- stage 1: starts completely fresh, empty of stage 0
COPY --from=builder <src> <dst>   <- reach back and take ONLY the finished artifact
```

Three things follow from this, and they are the whole reason the technique exists:

**1. Build tools and source never reach the final image.** The final image is built from its own base
and only receives what you explicitly `COPY --from`. The compiler, the package manager's cache, the
`.git` directory, the test fixtures, the `node_modules/.bin` full of dev tooling — none of it is
copied, so none of it exists. This is categorically different from `RUN ... && rm -rf ...`, which only
hides files behind a later layer; the bytes are still in the image and still pullable. A multi-stage
build does not delete the build environment — it never had it.

**2. Smaller attack surface.** This is the security argument and it is the one that matters most. Every
binary in an image is a tool available to an attacker who gets code execution in your container. A
container with `gcc`, `javac`, `curl`, `git` and a package manager is a comfortable place to pivot
from: download a payload, compile it, run it. A container holding one jar and a JRE is not. We proved
above that `javac` is genuinely absent from the multi-stage Java image and genuinely present in the
single-stage one. Fewer packages also means fewer CVEs for your scanner to report, and fewer
2 a.m. patch-and-redeploy cycles for vulnerabilities in software you were never even using.

**3. Faster pulls, faster everything.** The CONTENT SIZE column is the number that travels. Pulling
59.7 MB instead of 445 MB is roughly 7× less network per pull. Multiply that by every CI job, every
autoscaling event, every node in the cluster that has to pull the image cold before a pod can start.
Smaller images mean faster deploys, faster rollbacks, cheaper registry storage and cheaper egress.

A fourth benefit worth knowing: **stages build in parallel and cache independently**. BuildKit runs
independent stages concurrently, and a change to your source code invalidates only the layers after the
`COPY` of that source — the dependency-install stage stays cached. That is why `COPY package.json`
comes before `COPY server.js` in every Dockerfile here: dependencies change rarely, source changes
constantly, so the expensive step is ordered first and stays cached.

## Cleanup

```bash
docker rm -f hw06-main-app hw06-node hw06-python hw06-java
docker ps -a --filter 'name=hw06-'
```

```text
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
```

An empty table under the header means every container from this lab is gone. The images are kept so
the size comparison above can be re-checked at any time with
`docker images --filter=reference='hw06-*'`.
