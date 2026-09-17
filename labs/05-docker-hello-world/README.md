# Assignment 5 - Docker Fundamental: Hello World Applications

Six independent "Hello World" web applications, each in its own folder with its own Dockerfile.
Every image below was really built, really run and really verified with `curl` on this machine
(macOS, Apple Silicon / `linux/arm64`, Docker Engine 29.4.1 via Docker Desktop).

The outputs pasted in this document are copied from the terminal. BuildKit's per-layer byte-count
download lines (`sha256:... 3.15MB / 53.57MB`) have been trimmed because they are pure progress noise;
every step line, timing and result line is untouched.

---

## Summary

| App | Folder | Base image(s) | Host port | Container port | Image size | Status |
|---|---|---|---|---|---|---|
| Node.js | `nodejs-app/` | `node:24-alpine` | 3000 | 3000 | 249 MB | Passing |
| Python | `python-app/` | `python:3.12-slim` | 5001 | 5000 | 234 MB | Passing |
| Java | `java-app/` | `eclipse-temurin:21-jdk` -> `eclipse-temurin:21-jre` | 8080 | 8080 | 474 MB | Passing |
| Apache | `apache-app/` | `httpd:2.4` | 8081 | 80 | 205 MB | Passing |
| React | `react-app/` | `node:24-alpine` -> `nginx:alpine` | 8082 | 80 | 102 MB | Passing |
| Nginx | `nginx-app/` | `nginx:alpine` | 8083 | 80 | 102 MB | Passing |

Sizes come straight from `docker images`:

```bash
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}' | grep -E 'REPOSITORY|hw05-'
```

```text
REPOSITORY   TAG      IMAGE ID       SIZE
hw05-react   latest   0cc7282d409c   102MB
hw05-java    latest   0ea61238cf53   474MB
hw05-apache  latest   fcb5f18f08b8   205MB
hw05-nginx   latest   d0c8b1a7c251   102MB
hw05-python  latest   dc75a29ca85d   234MB
hw05-nodejs  latest   22d81457de1f   249MB
```

Two things worth noticing in that table before reading on:

- The two **multi-stage** images behave very differently. React drops to 102 MB because the heavy Node
  toolchain stays in the build stage and only the compiled `dist/` folder reaches the final Nginx image.
  Java stays at 474 MB because a JRE is simply a large runtime -- but the second stage still earns its
  keep. Building the same app single-stage on the JDK gives a **744 MB** image, so splitting it saved
  270 MB (see the Java section for that measurement).
- `alpine` versus `slim` versus the default Debian tag is the single biggest lever. `nginx:alpine`
  produces a 102 MB image for the same job that `httpd:2.4` (Debian-based) does in 205 MB.

---

## Why these six, and how they differ

They are deliberately three different shapes of containerised app:

1. **Static file servers** (Apache, Nginx) -- the Dockerfile is two lines. There is no application
   process to write; the base image already runs a web server, and you only drop a file into its
   document root. Note that neither Dockerfile has a `CMD`: the base image already declares one.
2. **Interpreted app servers** (Node.js, Python) -- you install dependencies at build time and then run
   the interpreter as the container's main process.
3. **Compiled app** (Java) -- source has to be compiled before it can run, which is the natural place
   for a multi-stage build. React is the same idea from the other direction: JSX gets compiled to plain
   static files, which then get handed to a static file server.

---

## 1. Node.js

**Source:** an Express app returning an HTML heading on port 3000.

### Dockerfile

```dockerfile
FROM node:24-alpine

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY server.js .

EXPOSE 3000

CMD ["npm", "start"]
```

Instruction by instruction:

- `FROM node:24-alpine` -- Alpine variant of the official Node image. It ships Node and npm on a musl
  Alpine base, so it is far smaller than `node:24` (Debian) for an app with no native dependencies.
- `WORKDIR /app` -- creates and switches to `/app`; every later relative path resolves against it.
- `COPY package*.json ./` **before** `COPY server.js .` -- this is the important ordering trick. Docker
  caches each layer, so as long as the dependency list has not changed, the `npm install` layer is
  reused and editing `server.js` rebuilds only the last two layers.
- `RUN npm install` -- installs Express into the image at build time, not at container start.
- `EXPOSE 3000` -- documentation metadata. It does **not** publish the port; `-p` on `docker run` does.
- `CMD ["npm", "start"]` -- exec form (a JSON array), which runs the command directly instead of wrapping
  it in `/bin/sh -c` as the shell form does.

A caveat worth knowing, checked rather than assumed. Even with the exec form, `npm start` means **npm**
is PID 1, not Node:

```bash
docker exec hw05-nodejs ps -o pid,ppid,args
```

```text
PID   PPID  COMMAND
    1     0 npm start
   18     1 {MainThread} node server.js
```

npm does not forward SIGTERM to its child, so `docker stop` waits the full 10-second grace period and
then kills the container. For a real service you would use `CMD ["node", "server.js"]` so Node itself is
PID 1 and can shut down cleanly. `npm start` is kept here because it is what the assignment's package
script defines, but the distinction is the useful takeaway.

### Build

```bash
cd homework/05-docker-hello-world/nodejs-app
docker build -t hw05-nodejs .
```

```text
#1 [internal] load build definition from Dockerfile
#1 DONE 0.0s
#2 [internal] load metadata for docker.io/library/node:24-alpine
#2 DONE 2.6s
#3 [internal] load .dockerignore
#3 DONE 0.0s
#4 [internal] load build context
#4 DONE 0.0s
#5 [1/5] FROM docker.io/library/node:24-alpine@sha256:50c8e8ca1d27439048670df5883f32d57cf81cff6233222c893fd0d9884cbd81
#5 DONE 7.9s
#6 [2/5] WORKDIR /app
#6 DONE 0.1s
#7 [3/5] COPY package*.json ./
#7 DONE 0.0s
#8 [4/5] RUN npm install
#8 2.294 added 68 packages, and audited 69 packages in 2s
#8 2.294 found 0 vulnerabilities
#8 DONE 2.4s
#9 [5/5] COPY server.js .
#9 DONE 0.0s
#10 exporting to image
#10 naming to docker.io/library/hw05-nodejs:latest done
#10 DONE 0.4s
```

### Run

```bash
docker run -d --name hw05-nodejs -p 3000:3000 hw05-nodejs
docker ps --filter name=hw05-nodejs
```

```text
a756f670d1d3f1094a7724edf45f8a0bd8be2b7b54d432d7556ecfb1e4b59630
CONTAINER ID   IMAGE         COMMAND                  CREATED         STATUS         PORTS                                         NAMES
a756f670d1d3   hw05-nodejs   "docker-entrypoint.s…"   5 minutes ago   Up 5 minutes   0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp   hw05-nodejs
```

### Verify

```bash
curl -i http://localhost:3000
```

```text
HTTP/1.1 200 OK
X-Powered-By: Express
Content-Type: text/html; charset=utf-8
Content-Length: 33
ETag: W/"21-kq9IZvWYTRKoU8szqxXzgIIvjbc"
Date: Thu, 17 Sep 2026 16:13:39 GMT
Connection: keep-alive
Keep-Alive: timeout=5

<h1>Hello World from Node.js</h1>
```

```bash
docker logs hw05-nodejs
```

```text
> nodejs-hello-world@1.0.0 start
> node server.js

Node.js server running on port 3000
```

The `X-Powered-By: Express` header confirms the response really came from the Express app and not from
some other process already listening on 3000.

---

## 2. Python

**Source:** a Flask app returning an HTML heading on port 5000.

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["python", "app.py"]
```

Instruction by instruction:

- `FROM python:3.12-slim` -- Debian-based but stripped of docs, man pages and build toolchain. `slim` is
  preferred over `python:3.12-alpine` here: Alpine uses musl instead of glibc, so many Python wheels have
  no prebuilt Alpine binary and pip falls back to compiling from source. `slim` gets you a small image
  without that trap.
- `COPY requirements.txt .` before `COPY app.py .` -- the same layer-cache ordering as the Node app.
- `RUN pip install --no-cache-dir -r requirements.txt` -- `--no-cache-dir` stops pip writing its
  download cache into the image, where it would only add dead weight to the layer.
- `CMD ["python", "app.py"]` -- runs Flask's built-in development server. Fine for a Hello World; a real
  deployment would front it with Gunicorn or uWSGI (Flask says so itself in the logs below).

One thing that is easy to miss: `app.py` binds to `host="0.0.0.0"`, not the default `127.0.0.1`. Inside a
container, `127.0.0.1` means "this container only", so a port mapping to it would never connect. Binding
to `0.0.0.0` is what makes the app reachable from the host.

### Build

```bash
cd homework/05-docker-hello-world/python-app
docker build -t hw05-python .
```

```text
#1 [internal] load build definition from Dockerfile
#1 DONE 0.0s
#2 [internal] load metadata for docker.io/library/python:3.12-slim
#2 DONE 3.8s
#3 [internal] load .dockerignore
#3 DONE 0.0s
#4 [internal] load build context
#4 DONE 0.0s
#5 [1/5] FROM docker.io/library/python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
#5 DONE 0.0s
#6 [2/5] WORKDIR /app
#6 DONE 0.1s
#7 [3/5] COPY requirements.txt .
#7 DONE 0.0s
#8 [4/5] RUN pip install --no-cache-dir -r requirements.txt
#8 DONE 3.4s
#9 [5/5] COPY app.py .
#9 DONE 0.0s
#10 exporting to image
#10 naming to docker.io/library/hw05-python:latest done
#10 DONE 0.5s
```

### Run

Note the asymmetric port mapping. On macOS, **host port 5000 is occupied by the AirPlay Receiver**
(`ControlCenter`), so the container's 5000 is published on host 5001 instead:

```bash
docker run -d --name hw05-python -p 5001:5000 hw05-python
docker ps --filter name=hw05-python
```

```text
729315e271ffe54e4e0ea0c0715e591160ea24c546376a12df74b5562927b1c2
CONTAINER ID   IMAGE         COMMAND           CREATED         STATUS         PORTS                                         NAMES
729315e271ff   hw05-python   "python app.py"   5 minutes ago   Up 5 minutes   0.0.0.0:5001->5000/tcp, [::]:5001->5000/tcp   hw05-python
```

### Verify

```bash
curl -i http://localhost:5001
```

```text
HTTP/1.1 200 OK
Server: Werkzeug/3.1.8 Python/3.12.14
Date: Thu, 17 Sep 2026 16:13:39 GMT
Content-Type: text/html; charset=utf-8
Content-Length: 32
Connection: close

<h1>Hello World from Python</h1>
```

```bash
docker logs hw05-python
```

```text
 * Serving Flask app 'app'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://172.17.0.5:5000
Press CTRL+C to quit
151.101.130.132 - - [17/Sep/2026 16:13:39] "GET / HTTP/1.1" 200 -
```

The last log line is the `curl` request arriving, and `Running on all addresses (0.0.0.0)` is the
`host="0.0.0.0"` bind proving itself.

---

## 3. Java

**Source:** `HelloWorld.java`, a single file using the JDK's built-in `com.sun.net.httpserver.HttpServer`
on port 8080. No Maven, no Gradle, no dependencies -- the whole app is one `.java` file, which keeps the
focus on the Docker mechanics.

### Dockerfile

```dockerfile
FROM eclipse-temurin:21-jdk AS builder

WORKDIR /build

COPY HelloWorld.java .

RUN javac HelloWorld.java

FROM eclipse-temurin:21-jre

WORKDIR /app

COPY --from=builder /build/HelloWorld.class .

EXPOSE 8080

CMD ["java", "HelloWorld"]
```

This is the only app here that genuinely needs two stages, and it shows the pattern clearly:

- `FROM eclipse-temurin:21-jdk AS builder` -- Eclipse Temurin is the Adoptium OpenJDK distribution. It is
  used instead of the deprecated `openjdk` Docker Hub image, and it publishes proper `linux/arm64`
  images, which matters on Apple Silicon. `AS builder` names the stage so the second stage can reach
  back into it.
- `RUN javac HelloWorld.java` -- **the compile happens inside the image**, which is why you do not need a
  JDK installed on your laptop to build this. That is the real selling point of containerising a build.
- `FROM eclipse-temurin:21-jre` -- a second, independent stage. A JRE can run bytecode but cannot compile
  it, so it omits `javac`, the compiler internals and the JDK tooling.
- `COPY --from=builder /build/HelloWorld.class .` -- copies **only** the compiled artifact across. The
  `.java` source and the entire JDK stay behind and never reach the shipped image.
- `CMD ["java", "HelloWorld"]` -- note there is no `.class` extension; `java` takes a class name.

### Build

```bash
cd homework/05-docker-hello-world/java-app
docker build -t hw05-java .
```

```text
#1 [internal] load build definition from Dockerfile
#1 DONE 0.0s
#2 [internal] load metadata for docker.io/library/eclipse-temurin:21-jdk
#2 DONE 3.8s
#3 [internal] load metadata for docker.io/library/eclipse-temurin:21-jre
#3 DONE 3.8s
#4 [internal] load .dockerignore
#4 DONE 0.0s
#5 [internal] load build context
#5 DONE 0.0s
#6 [stage-1 1/3] FROM docker.io/library/eclipse-temurin:21-jre@sha256:6cbdfc89c9657478bc5abea638030310f6c0267404e98a5808097bb1925932f1
#6 DONE 60.4s
#7 [builder 1/4] FROM docker.io/library/eclipse-temurin:21-jdk@sha256:78ab9771b4650066c3ef748d46e05dbd6094d8bb34e0667a074486812efd655b
#7 DONE 115.6s
#8 [stage-1 2/3] WORKDIR /app
#8 DONE 0.4s
#9 [builder 2/4] WORKDIR /build
#9 DONE 0.2s
#10 [builder 3/4] COPY HelloWorld.java .
#10 DONE 0.0s
#11 [builder 4/4] RUN javac HelloWorld.java
#11 DONE 0.5s
#12 [stage-1 3/3] COPY --from=builder /build/HelloWorld.class .
#12 DONE 0.0s
#13 exporting to image
#13 naming to docker.io/library/hw05-java:latest done
#13 DONE 0.1s
```

Two details are visible here that do not appear in any single-stage build:

- Steps `#6` and `#7` ran **at the same time**. BuildKit builds a dependency graph rather than a
  top-to-bottom script, so the JRE base image downloaded while the JDK base image was still pulling.
- The JDK pull took 115.6 s against 60.4 s for the JRE -- roughly the size difference that the second
  stage exists to avoid shipping.

### Size check: what the second stage actually bought

Building the exact same app single-stage on the JDK, for comparison:

```bash
cat > /tmp/Dockerfile.singlestage <<'EOF'
FROM eclipse-temurin:21-jdk
WORKDIR /app
COPY HelloWorld.java .
RUN javac HelloWorld.java
EXPOSE 8080
CMD ["java", "HelloWorld"]
EOF

docker build -f /tmp/Dockerfile.singlestage -t hw05-java-singlestage ./java-app
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | grep -E 'REPOSITORY|hw05-java'
```

The Dockerfile is written to `/tmp` and pointed at with `-f`, while the build context stays `./java-app`.
Piping the Dockerfile into `docker build -` would not work here: that form sends an **empty** context, so
`COPY HelloWorld.java .` would fail with `file not found`.

```text
REPOSITORY              TAG      SIZE
hw05-java-singlestage   latest   744MB
hw05-java               latest   474MB
```

744 MB against 474 MB: the two-stage split removed **270 MB**, about 36% of the image, for four extra
lines of Dockerfile. That saving is the JDK's compiler and tooling, which the running app never needs.
It is also a smaller attack surface -- a shipped `javac` is a compiler an attacker could use.

### Run

```bash
docker run -d --name hw05-java -p 8080:8080 hw05-java
docker ps --filter name=hw05-java
```

```text
77480573ada4b47dae96a50a78a721da830f1a3f2d2d563b4b0203c9c0d411fc
CONTAINER ID   IMAGE       COMMAND                  CREATED                  STATUS                  PORTS                                         NAMES
77480573ada4   hw05-java   "/__cacert_entrypoin…"   Less than a second ago   Up Less than a second   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp   hw05-java
```

The `COMMAND` column shows `/__cacert_entrypoin…`, not `java HelloWorld`. That is Temurin's own
`ENTRYPOINT`, which fixes up the CA certificate store before handing off to whatever `CMD` you set. It
is a good reminder that `CMD` supplies arguments to an inherited `ENTRYPOINT` rather than replacing it.

### Verify

```bash
curl -i http://localhost:8080
```

```text
HTTP/1.1 200 OK
Date: Thu, 17 Sep 2026 16:21:09 GMT
Content-type: text/html
Content-length: 30

<h1>Hello World from Java</h1>
```

```bash
docker logs hw05-java
```

```text
Java server running on port 8080
```

That single log line is the `System.out.println` at the end of `main`, which proves the JVM started, the
class the JRE stage received is the one that was compiled in the builder stage, and the socket bound
successfully.

---

## 4. Apache

**Source:** a static `index.html`.

### Dockerfile

```dockerfile
FROM httpd:2.4

COPY index.html /usr/local/apache2/htdocs/index.html

EXPOSE 80
```

- `FROM httpd:2.4` -- the official Apache HTTP Server image. The version is pinned to `2.4` rather than
  using `latest`, so a future major release cannot silently change the image under you.
- `COPY index.html /usr/local/apache2/htdocs/index.html` -- `htdocs` is Apache's document root in this
  image. Apache's path differs from Nginx's (`/usr/share/nginx/html`), and putting the file in the wrong
  one is the classic mistake here: you get Apache's default "It works!" page instead of your own.
- **No `CMD`.** The base image already sets `CMD ["httpd-foreground"]`. Redefining it would only risk
  getting it wrong. `httpd-foreground` matters because a container dies when PID 1 exits, so the server
  must run in the foreground rather than daemonising.

This image is 205 MB, roughly double the Nginx one, because the plain `2.4` tag is Debian-based. An
Alpine variant **is** published -- `httpd:2.4-alpine` -- and swapping the `FROM` line for it (the `COPY`
path is unchanged) would cut the image to a similar size as the Nginx one. The Debian tag is kept here
deliberately, so the summary table shows what the base-image choice alone costs you: same two-line
Dockerfile, same result, double the size.

### Build

```bash
cd homework/05-docker-hello-world/apache-app
docker build -t hw05-apache .
```

```text
#1 [internal] load build definition from Dockerfile
#1 DONE 0.0s
#2 [internal] load metadata for docker.io/library/httpd:2.4
#2 DONE 1.6s
#3 [internal] load .dockerignore
#3 DONE 0.0s
#4 [internal] load build context
#4 DONE 0.0s
#5 [1/2] FROM docker.io/library/httpd:2.4@sha256:979c38c2228d28c2edfd45c6e27dcee1c7b4a101a5526721ae8ece454e89e99e
#5 DONE 0.0s
#6 [2/2] COPY index.html /usr/local/apache2/htdocs/index.html
#6 DONE 0.0s
#7 exporting to image
#7 naming to docker.io/library/hw05-apache:latest done
#7 DONE 0.1s
```

### Run

```bash
docker run -d --name hw05-apache -p 8081:80 hw05-apache
docker ps --filter name=hw05-apache
```

```text
3079ce4ea3c58e5321a4799410894885cfd30801ab33edea0fd4b2d16b03b61a
CONTAINER ID   IMAGE         COMMAND              CREATED         STATUS         PORTS                                     NAMES
3079ce4ea3c5   hw05-apache   "httpd-foreground"   5 minutes ago   Up 5 minutes   0.0.0.0:8081->80/tcp, [::]:8081->80/tcp   hw05-apache
```

The `COMMAND` column shows `httpd-foreground`, inherited from the base image exactly as described above.

### Verify

```bash
curl -i http://localhost:8081
```

```text
HTTP/1.1 200 OK
Date: Thu, 17 Sep 2026 16:13:39 GMT
Server: Apache/2.4.68 (Unix)
Last-Modified: Thu, 17 Sep 2026 14:43:21 GMT
ETag: "ad-65baece217440"
Accept-Ranges: bytes
Content-Length: 173
Content-Type: text/html

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Apache Hello World</title>
</head>
<body>
    <h1>Hello World from Apache</h1>
</body>
</html>
```

```bash
docker logs hw05-apache
```

```text
AH00558: httpd: Could not reliably determine the server's fully qualified domain name, using 172.17.0.6. Set the 'ServerName' directive globally to suppress this message
[Thu Sep 17 16:13:16.989005 2026] [mpm_event:notice] [pid 1:tid 1] AH00489: Apache/2.4.68 (Unix) configured -- resuming normal operations
[Thu Sep 17 16:13:16.989351 2026] [core:notice] [pid 1:tid 1] AH00094: Command line: 'httpd -D FOREGROUND'
151.101.130.132 - - [17/Sep/2026:16:13:39 +0000] "GET / HTTP/1.1" 200 173
```

The `AH00558` line is a harmless warning, not an error: the container has no DNS name, so Apache falls
back to its IP. `pid 1` on the notice line confirms httpd really is PID 1 in the container.

---

## 5. React

**Source:** a Vite + React app whose `App.jsx` renders `<h1>Hello World from React</h1>`.

### Dockerfile

```dockerfile
FROM node:24-alpine AS builder

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
```

The key insight: **React is not a server.** `npm run build` turns JSX into plain HTML, CSS and JS, and
those files need nothing more than a static file server. So the build stage does the compiling, and the
runtime stage is just the Nginx app from section 6 with different content.

- `FROM node:24-alpine AS builder` -- Node only exists to run Vite. It never ships.
- `COPY package*.json ./` then `RUN npm install` then `COPY . .` -- again the cache ordering. Here it
  matters more than anywhere else, because `npm install` for this app takes 26 seconds against 1.1
  seconds for the actual build.
- `RUN npm run build` -- produces `/app/dist`.
- `FROM nginx:alpine` -- the runtime stage starts from scratch; nothing from the builder carries over
  except what is explicitly copied.
- `COPY --from=builder /app/dist /usr/share/nginx/html` -- the finished static bundle replaces Nginx's
  default page.

There is also a `.dockerignore` containing `node_modules` and `dist`. Without it, `COPY . .` would upload
a local `node_modules` into the build context -- slow, and it would shadow the Linux-native modules
`npm install` just built inside the image.

### Build

```bash
cd homework/05-docker-hello-world/react-app
docker build -t hw05-react .
```

```text
#1 [internal] load build definition from Dockerfile
#1 DONE 0.0s
#2 [internal] load metadata for docker.io/library/nginx:alpine
#2 DONE 0.0s
#3 [internal] load metadata for docker.io/library/node:24-alpine
#3 DONE 0.7s
#5 [internal] load .dockerignore
#5 DONE 0.0s
#6 [internal] load build context
#6 DONE 0.0s
#8 [builder 3/6] COPY package*.json ./
#8 DONE 0.1s
#9 [stage-1 1/2] FROM docker.io/library/nginx:alpine@sha256:c8497b180665e631ec92a5091125bec5b214f0e2b99409e30653a125b37557da
#9 DONE 0.1s
#10 [builder 4/6] RUN npm install
#10 25.58 added 64 packages, and audited 65 packages in 25s
#10 25.58 found 0 vulnerabilities
#10 DONE 26.0s
#11 [builder 5/6] COPY . .
#11 DONE 0.1s
#12 [builder 6/6] RUN npm run build
#12 0.196 > react-hello-world@1.0.0 build
#12 0.196 > vite build
#12 0.331 vite v6.4.3 building for production...
#12 0.368 transforming...
#12 0.920 ✓ 28 modules transformed.
#12 1.002 rendering chunks...
#12 1.007 computing gzip size...
#12 1.013 dist/index.html                  0.24 kB │ gzip:  0.20 kB
#12 1.013 dist/assets/index-DPNYE6g9.js  224.10 kB │ gzip: 69.59 kB
#12 1.014 ✓ built in 666ms
#12 DONE 1.1s
#13 [stage-1 2/2] COPY --from=builder /app/dist /usr/share/nginx/html
#13 DONE 0.0s
#14 exporting to image
#14 naming to docker.io/library/hw05-react:latest done
#14 DONE 0.1s
```

`RUN npm install` needs working internet access inside the build. On a machine behind a proxy or with no
network, this is the step that fails.

The Vite summary is the whole point of the multi-stage split: the entire app ships as one 224 kB JS file
plus a 0.24 kB HTML file. The final image is 102 MB -- essentially just `nginx:alpine`.

### Run

```bash
docker run -d --name hw05-react -p 8082:80 hw05-react
docker ps --filter name=hw05-react
```

```text
504f2133d576107f833b1e849bfb0017e51f9eecf7008ee8dc847b15dd374aae
CONTAINER ID   IMAGE        COMMAND                  CREATED         STATUS         PORTS                                     NAMES
504f2133d576   hw05-react   "/docker-entrypoint.…"   5 minutes ago   Up 5 minutes   0.0.0.0:8082->80/tcp, [::]:8082->80/tcp   hw05-react
```

### Verify

```bash
curl -i http://localhost:8082
```

```text
HTTP/1.1 200 OK
Server: nginx/1.31.6
Date: Thu, 17 Sep 2026 16:13:39 GMT
Content-Type: text/html
Content-Length: 239
Last-Modified: Thu, 17 Sep 2026 16:13:04 GMT
Connection: keep-alive
ETag: "6aac1190-ef"
Accept-Ranges: bytes

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>React Hello World</title>
  <script type="module" crossorigin src="/assets/index-DPNYE6g9.js"></script>
</head>
<body>
    <div id="root"></div>
</body>
</html>
```

**This is the one app where `curl` does not print the Hello World text, and that is correct behaviour.**
React renders in the browser: the server sends an empty `<div id="root">` plus a script tag, and the
heading only exists after JavaScript runs. `curl` does not run JavaScript.

Notice too that Vite rewrote `src="/src/main.jsx"` in the source `index.html` into the hashed production
bundle path. That rewrite is what `npm run build` did.

To prove from the command line that the text really shipped, fetch the bundle Nginx is serving:

```bash
curl -s http://localhost:8082/assets/index-DPNYE6g9.js | grep -o 'Hello World from React'
```

```text
Hello World from React
```

```bash
docker logs hw05-react
```

```text
151.101.130.132 - - [17/Sep/2026:16:13:39 +0000] "GET / HTTP/1.1" 200 239 "-" "curl/8.7.1" "-"
151.101.130.132 - - [17/Sep/2026:16:13:46 +0000] "GET /assets/index-DPNYE6g9.js HTTP/1.1" 200 224096 "-" "curl/8.7.1" "-"
```

Both requests returned 200. Opening <http://localhost:8082> in a browser shows the rendered heading.

---

## 6. Nginx

**Source:** a static `index.html`.

### Dockerfile

```dockerfile
FROM nginx:alpine

COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80
```

- `FROM nginx:alpine` -- the Alpine variant, chosen because a static file server has no reason to carry a
  full Debian userland. At 102 MB it is the smallest image in this assignment, tied with the React one
  that is built on top of it.
- `COPY index.html /usr/share/nginx/html/index.html` -- Nginx's default document root, per the default
  server block shipped in the image. This overwrites the stock Nginx welcome page.
- No `CMD` -- the base image already runs `nginx -g 'daemon off;'`, keeping Nginx in the foreground so
  the container stays alive.

Compare this with the Apache section: identical two-line pattern, different document root, half the size
-- and the size gap comes entirely from `alpine` versus Debian, not from Nginx being lighter than Apache.
That side-by-side is the main lesson of having both.

### Build

```bash
cd homework/05-docker-hello-world/nginx-app
docker build -t hw05-nginx .
```

```text
#1 [internal] load build definition from Dockerfile
#1 DONE 0.0s
#2 [internal] load metadata for docker.io/library/nginx:alpine
#2 DONE 0.0s
#3 [internal] load .dockerignore
#3 DONE 0.0s
#4 [internal] load build context
#4 DONE 0.0s
#5 [1/2] FROM docker.io/library/nginx:alpine@sha256:72ba65eb42c10344912a84ff42408db7d34f2feb642204570ab8fc5ffd29f1d3
#5 DONE 0.0s
#6 [2/2] COPY index.html /usr/share/nginx/html/index.html
#6 DONE 0.0s
#7 exporting to image
#7 naming to docker.io/library/hw05-nginx:latest done
#7 DONE 0.1s
```

Step `#2` took 0.0 s because `nginx:alpine` was already resolved and present locally. Only the tiny
`COPY` layer is new, which is why `hw05-nginx` and `hw05-react` are both about 102 MB: they share the
same Nginx base layers on disk rather than storing two copies.

### Run

```bash
docker run -d --name hw05-nginx -p 8083:80 hw05-nginx
docker ps --filter name=hw05-nginx
```

```text
708609f7bc449bab38a72ac55c31c9fda6515562ffc0d69712cb9c2eede9befa
CONTAINER ID   IMAGE        COMMAND                  CREATED         STATUS         PORTS                                     NAMES
708609f7bc44   hw05-nginx   "/docker-entrypoint.…"   5 minutes ago   Up 5 minutes   0.0.0.0:8083->80/tcp, [::]:8083->80/tcp   hw05-nginx
```

### Verify

```bash
curl -i http://localhost:8083
```

```text
HTTP/1.1 200 OK
Server: nginx/1.31.5
Date: Thu, 17 Sep 2026 16:13:39 GMT
Content-Type: text/html
Content-Length: 171
Last-Modified: Thu, 17 Sep 2026 14:43:21 GMT
Connection: keep-alive
ETag: "6aabfc89-ab"
Accept-Ranges: bytes

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nginx Hello World</title>
</head>
<body>
    <h1>Hello World from Nginx</h1>
</body>
</html>
```

```bash
docker logs hw05-nginx
```

```text
151.101.130.132 - - [17/Sep/2026:16:13:39 +0000] "GET / HTTP/1.1" 200 171 "-" "curl/8.7.1" "-"
```

---

## All six running at once

This is the `docker ps` for the whole assignment:

```bash
docker ps --filter name=hw05- --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

```text
NAMES         IMAGE         STATUS         PORTS
hw05-java     hw05-java     Up 6 seconds   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp
hw05-nginx    hw05-nginx    Up 7 minutes   0.0.0.0:8083->80/tcp, [::]:8083->80/tcp
hw05-react    hw05-react    Up 7 minutes   0.0.0.0:8082->80/tcp, [::]:8082->80/tcp
hw05-apache   hw05-apache   Up 7 minutes   0.0.0.0:8081->80/tcp, [::]:8081->80/tcp
hw05-python   hw05-python   Up 7 minutes   0.0.0.0:5001->5000/tcp, [::]:5001->5000/tcp
hw05-nodejs   hw05-nodejs   Up 7 minutes   0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp
```

Six containers, six ports, one Docker host. `hw05-java` shows a shorter uptime than the rest because it
had to be restarted after the port conflict described in the troubleshooting section.

---

## Run everything

From the `homework/05-docker-hello-world` directory:

```bash
docker build -t hw05-nodejs ./nodejs-app
docker build -t hw05-python ./python-app
docker build -t hw05-java   ./java-app
docker build -t hw05-apache ./apache-app
docker build -t hw05-react  ./react-app
docker build -t hw05-nginx  ./nginx-app

docker run -d --name hw05-nodejs -p 3000:3000 hw05-nodejs
docker run -d --name hw05-python -p 5001:5000 hw05-python
docker run -d --name hw05-java   -p 8080:8080 hw05-java
docker run -d --name hw05-apache -p 8081:80   hw05-apache
docker run -d --name hw05-react  -p 8082:80   hw05-react
docker run -d --name hw05-nginx  -p 8083:80   hw05-nginx

docker ps --filter name=hw05-
```

Smoke-test all six in one loop:

```bash
for p in 3000 5001 8080 8081 8082 8083; do
  echo "--- localhost:$p ---"
  curl -s http://localhost:$p | grep -o 'Hello World from [A-Za-z.]*' || echo "(React: text is in the JS bundle, open in a browser)"
done
```

Real output from this repository:

```text
--- localhost:3000 ---
Hello World from Node.js
--- localhost:5001 ---
Hello World from Python
--- localhost:8080 ---
Hello World from Java
--- localhost:8081 ---
Hello World from Apache
--- localhost:8082 ---
(React: text is in the JS bundle, open in a browser)
--- localhost:8083 ---
Hello World from Nginx
```

Open in a browser:

| URL | Expected |
|---|---|
| <http://localhost:3000> | Hello World from Node.js |
| <http://localhost:5001> | Hello World from Python |
| <http://localhost:8080> | Hello World from Java |
| <http://localhost:8081> | Hello World from Apache |
| <http://localhost:8082> | Hello World from React |
| <http://localhost:8083> | Hello World from Nginx |

## Clean up everything

```bash
docker rm -f hw05-nodejs hw05-python hw05-java hw05-apache hw05-react hw05-nginx
```

Or, to catch every container whose name starts with `hw05-` in one go:

```bash
docker rm -f $(docker ps -aq --filter name=hw05-)
```

`docker rm -f` stops and removes in a single step; without `-f` you would need `docker stop` first.

Verify nothing is left:

```bash
docker ps -a | grep hw05
```

```text
```

(Empty output means every container is gone.)

To remove the images as well:

```bash
docker rmi hw05-nodejs hw05-python hw05-java hw05-apache hw05-react hw05-nginx
```

---

## Troubleshooting: problems actually hit while doing this

### 1. Port 5000 is taken on macOS, and nothing is obviously using it

Publishing Flask on host port 5000 fails, or worse, appears to succeed and then returns a 403 from
something that is clearly not Flask. macOS runs the **AirPlay Receiver** on port 5000.

```bash
lsof -nP -iTCP:5000 -sTCP:LISTEN
```

```text
COMMAND     PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
ControlCe   552 aman   11u  IPv4 0x925a3171ffd61fd6      0t0  TCP *:5000 (LISTEN)
ControlCe   552 aman   12u  IPv6 0xc5c2b891dee1ce0e      0t0  TCP *:5000 (LISTEN)
```

`ControlCe` is macOS Control Center. Fix: publish on a different **host** port. The container port stays
5000; only the left-hand side of `-p` changes, so no application code is touched:

```bash
docker run -d --name hw05-python -p 5001:5000 hw05-python
```

The alternative is turning off AirPlay Receiver in System Settings > General > AirDrop & Handoff, but
remapping the host port is less invasive and is the habit worth building.

### 2. `port is already allocated`

Hit while starting the Java container, because a container from a different exercise was already bound to
8080:

```text
docker: Error response from daemon: failed to set up container networking: driver failed programming
external connectivity on endpoint hw05-java: Bind for 0.0.0.0:8080 failed: port is already allocated
```

Find the culprit before doing anything destructive:

```bash
docker ps --format '{{.Names}} {{.Ports}}' | grep 8080
```

Then either stop that container, or publish on a free host port (`-p 8090:8080`).

An important detail: after this failure the container still **exists** in `Created` state, so a plain
retry fails again with `Conflict. The container name "/hw05-java" is already in use`. Clear it first:

```bash
docker rm -f hw05-java
```

If you want to test the app without competing for a host port at all, skip `-p` entirely and reach the
container from inside Docker's own network:

```bash
docker run -d --name hw05-java hw05-java
docker run --rm --network container:hw05-java curlimages/curl -s -i http://localhost:8080
```

```text
HTTP/1.1 200 OK
Date: Thu, 17 Sep 2026 16:15:34 GMT
Content-type: text/html
Content-length: 30

<h1>Hello World from Java</h1>
```

`--network container:<name>` puts the throwaway curl container in the target's network namespace, so
`localhost` there is the app itself. This is a genuinely useful debugging move: it isolates "is the app
broken?" from "is the port mapping broken?".

### 3. `curl` returns nothing at all, but the container says it is running

Almost always the app bound to `127.0.0.1` inside the container. From the container's point of view,
`127.0.0.1` is the container itself, so the published port has nothing to forward to. Web apps in
containers must bind `0.0.0.0`. In `python-app/app.py` that is the explicit `host="0.0.0.0"`.

Confirm the process is really listening on all interfaces:

```bash
docker logs hw05-python | head -5
```

### 4. React's page loads but `curl` shows no Hello World

Not a bug. See the React section: the heading is produced by JavaScript in the browser, and the server
only ever sends an empty root div. Verify by fetching the bundle and grepping it, or just open the page in
a browser. The same thing happens with Angular and Vue.

### 5. `exec format error` on Apple Silicon

Not hit here, but this is the arm64 trap worth knowing about. `httpd:2.4`, `eclipse-temurin:21-*`,
`node:24-alpine`, `python:3.12-slim` and `nginx:alpine` all publish native `linux/arm64` images, so
everything ran natively. When an image is amd64-only, Docker either refuses or runs it slowly under
emulation. Check what you actually have:

```bash
docker image inspect hw05-java --format '{{.Os}}/{{.Architecture}}'
```

```text
linux/arm64
```

If an image has no arm64 build, force emulation explicitly:

```bash
docker build --platform linux/amd64 -t hw05-something .
```

### 6. Editing source does not change the running container

Containers run the image, not your working directory. Rebuild and recreate:

```bash
docker rm -f hw05-nodejs
docker build -t hw05-nodejs ./nodejs-app
docker run -d --name hw05-nodejs -p 3000:3000 hw05-nodejs
```

If the rebuild seems to ignore your change, it is usually the layer cache being cleverer than you want:

```bash
docker build --no-cache -t hw05-nodejs ./nodejs-app
```

### 7. `npm install` fails during the React build

The build stage needs internet access. Symptoms are `ETIMEDOUT`, `ENOTFOUND registry.npmjs.org` or an
`npm ERR! network` message. Confirm Docker itself has DNS:

```bash
docker run --rm alpine ping -c 1 registry.npmjs.org
```

Behind a corporate proxy, pass the proxy into the build with
`--build-arg HTTP_PROXY=... --build-arg HTTPS_PROXY=...`.
