# Multi-stage build — deploying three app types

> Real session — every command was executed and the output is verbatim.

[← Back](README.md)

---

```console
# --- Deliberately different stack from docker-fundamentals: each app here
# --- exposes a real JSON API (/api/info) plus an HTML page (/), uses a
# --- real dependency (Express / Flask / org.json via Maven), reports its
# --- own language + runtime + framework version, and is itself built as a
# --- multi-stage image - reinforcing this topic's theme. ---
```

### 3.1 Node.js + Express (multi-stage: npm-install stage -> slim runtime)

```console
root@ubuntu-hw:~/03-application-deployment/nodejs# cat Dockerfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json .
RUN npm install --omit=dev --no-audit --no-fund

FROM node:22-alpine
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json server.js ./
EXPOSE 3000
USER node
CMD ["node", "server.js"]

root@ubuntu-hw:~/03-application-deployment/nodejs# docker build -t ms-deploy-node:latest .
#0 building with "desktop-linux" instance using docker driver

#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 681B done
#1 DONE 0.0s

#2 [internal] load metadata for docker.io/library/node:22-alpine
#2 DONE 0.0s

#4 [deps 1/4] FROM docker.io/library/node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32
#4 DONE 0.0s

#6 [deps 2/4] WORKDIR /app
#6 CACHED

#7 [deps 3/4] COPY package.json .
#7 DONE 0.0s

#8 [deps 4/4] RUN npm install --omit=dev --no-audit --no-fund
#8 2.016
#8 2.016 added 68 packages in 2s
#8 DONE 2.1s

#9 [stage-1 3/4] COPY --from=deps /app/node_modules ./node_modules
#9 DONE 0.1s

#10 [stage-1 4/4] COPY package.json server.js ./
#10 DONE 0.0s

#11 exporting to image
#11 naming to docker.io/library/ms-deploy-node:latest done
#11 DONE 0.3s
```

### 3.2 Python + Flask (multi-stage: venv-build stage -> slim runtime)

```console
root@ubuntu-hw:~/03-application-deployment/python# cat Dockerfile
FROM python:3.12-alpine AS builder
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-alpine
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY app.py .
EXPOSE 5000
RUN adduser -D appuser
USER appuser
CMD ["python", "app.py"]

root@ubuntu-hw:~/03-application-deployment/python# docker build -t ms-deploy-python:latest .
#0 building with "desktop-linux" instance using docker driver
...
#7 [builder 3/5] RUN python -m venv /opt/venv
#7 DONE 2.7s

#8 [builder 4/5] COPY requirements.txt .
#8 DONE 0.0s

#9 [builder 5/5] RUN pip install --no-cache-dir -r requirements.txt
#9 0.508 Collecting flask==3.0.3 (from -r requirements.txt (line 1))
#9 4.688   Downloading flask-3.0.3-py3-none-any.whl.metadata (3.2 kB)
#9 5.361 Installing collected packages: MarkupSafe, itsdangerous, click, blinker, Werkzeug, Jinja2, flask
#9 5.736 Successfully installed Jinja2-3.1.6 MarkupSafe-3.0.3 Werkzeug-3.1.8 blinker-1.9.0 click-8.5.0 flask-3.0.3 itsdangerous-2.2.0
#9 DONE 5.9s

#10 [stage-1 3/5] COPY --from=builder /opt/venv /opt/venv
#10 DONE 0.2s

#11 [stage-1 4/5] COPY app.py .
#11 DONE 0.0s

#12 [stage-1 5/5] RUN adduser -D appuser
#12 DONE 0.1s

#13 exporting to image
#13 naming to docker.io/library/ms-deploy-python:latest done
#13 DONE 0.8s
```

### 3.3 Java + Maven (multi-stage: JDK+Maven builder -> JRE-only runtime)

```console
root@ubuntu-hw:~/03-application-deployment/java# cat Dockerfile
FROM maven:3.9-eclipse-temurin-21-alpine AS builder
WORKDIR /build
COPY pom.xml .
COPY src ./src
RUN mvn -B -q -DskipTests package

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=builder /build/target/ms-deploy-java.jar ./app.jar
EXPOSE 8080
RUN addgroup -S app && adduser -S app -G app
USER app
CMD ["java", "-jar", "app.jar"]

root@ubuntu-hw:~/03-application-deployment/java# docker build -t ms-deploy-java:latest .
#0 building with "desktop-linux" instance using docker driver
...
#8 [builder 1/5] FROM docker.io/library/maven:3.9-eclipse-temurin-21-alpine@sha256:65353f527c86cb23187c8233475713e15067e8d36220d18863c379680698fe85
#8 DONE 2.9s

#9 [builder 2/5] WORKDIR /build
#9 DONE 0.1s

#10 [builder 3/5] COPY pom.xml .
#10 DONE 0.0s

#11 [builder 4/5] COPY src ./src
#11 DONE 0.0s

#12 [builder 5/5] RUN mvn -B -q -DskipTests package
#12 DONE 16.3s

# --- mvn resolved org.json:json:20240303 and the shade plugin from Maven
# --- Central during this step and packaged a self-contained shaded jar. ---

#13 [stage-1 3/4] COPY --from=builder /build/target/ms-deploy-java.jar ./app.jar
#13 DONE 0.0s

#14 [stage-1 4/4] RUN addgroup -S app && adduser -S app -G app
#14 DONE 0.1s

#15 exporting to image
#15 naming to docker.io/library/ms-deploy-java:latest done
#15 DONE 0.1s
```

### Running all three (mapped to the assigned host ports) and verifying

```console
root@ubuntu-hw:~# docker run -d --name ms-deploy-node -p 18091:3000 ms-deploy-node:latest
71922f440db214822a024a4a027092ee569d7386457370dbb5a16ce10230e6f8
root@ubuntu-hw:~# docker run -d --name ms-deploy-python -p 18092:5000 ms-deploy-python:latest
250d945db0a0156ab75d7ee230e5351fb364559c75daddc89d7c8789ea8ee846
root@ubuntu-hw:~# docker run -d --name ms-deploy-java -p 18093:8080 ms-deploy-java:latest
88cd045f70a316c7e91960af9ddf4d832378b0fded376877cd9b95cc64c5bcdd

root@ubuntu-hw:~# docker ps --filter "name=ms-"
CONTAINER ID   IMAGE                     COMMAND                  CREATED          STATUS          PORTS                                           NAMES
88cd045f70a3   ms-deploy-java:latest     "/__cacert_entrypoin…"   2 seconds ago    Up 2 seconds    0.0.0.0:18093->8080/tcp, [::]:18093->8080/tcp   ms-deploy-java
250d945db0a0   ms-deploy-python:latest   "python app.py"          3 seconds ago    Up 2 seconds    0.0.0.0:18092->5000/tcp, [::]:18092->5000/tcp   ms-deploy-python
71922f440db2   ms-deploy-node:latest     "docker-entrypoint.s…"   3 seconds ago    Up 2 seconds    0.0.0.0:18091->3000/tcp, [::]:18091->3000/tcp   ms-deploy-node
cbe6e719ba32   ms-app:multistage         "/app"                   About a minute ago   Up About a minute   0.0.0.0:18090->8080/tcp, [::]:18090->8080/tcp   ms-app

# --- All four of this section's containers running together, each on its
# --- own assigned host port, none clashing. ---

root@ubuntu-hw:~# curl -s http://localhost:18091/api/info
{"app":"ms-deploy-node","language":"Node.js","runtime":"v22.23.2","framework":"Express 4.22.2","hostname":"71922f440db2","platform":"Linux arm64","timestamp":"2026-09-02T17:31:57.233Z"}

root@ubuntu-hw:~# curl -s http://localhost:18092/api/info
{"app":"ms-deploy-python","framework":"Flask 3.0.3","hostname":"250d945db0a0","language":"Python","platform":"Linux aarch64","runtime":"CPython 3.12.14","timestamp":"2026-09-02T17:31:57.256838+00:00"}

root@ubuntu-hw:~# curl -s http://localhost:18093/api/info
{
  "app": "ms-deploy-java",
  "hostname": "88cd045f70a3",
  "framework": "org.json 20240303",
  "runtime": "JRE 21.0.12",
  "language": "Java",
  "platform": "Linux aarch64",
  "timestamp": "2026-09-02T17:31:57.282163917Z"
}

root@ubuntu-hw:~# curl -s http://localhost:18091/ | head -5
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Node.js Deployment Demo</title>

root@ubuntu-hw:~# curl -s http://localhost:18092/ | head -5
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Python Deployment Demo</title>

root@ubuntu-hw:~# curl -s http://localhost:18093/ | head -6
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Java Deployment Demo</title>
<style>body{font-family:sans-serif;background:#1b1b2f;color:#eaeaea;text-align:center;padding-top:70px;}h1{font-size:2.6em;color:#e94560;}p{color:#9a9ab0;}code{background:#162447;padding:2px 8px;border-radius:4px;}</style></head>
<body>
<h1>Java Deployment Demo</h1>

root@ubuntu-hw:~# docker logs ms-deploy-node
ms-deploy-node listening on port 3000 (Node v22.23.2, Express 4.22.2)

root@ubuntu-hw:~# docker logs ms-deploy-java
ms-deploy-java listening on port 8080 (JRE 21.0.12)

root@ubuntu-hw:~# docker logs ms-deploy-python
 * Serving Flask app 'app'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://172.17.0.14:5000
Press CTRL+C to quit
/app/app.py:21: DeprecationWarning: The '__version__' attribute is deprecated and will be removed in Flask 3.1. Use feature detection or 'importlib.metadata.version("flask")' instead.
  framework=f"Flask {flask.__version__}",
192.168.65.1 - - [02/Sep/2026 17:31:57] "GET /api/info HTTP/1.1" 200 -

# --- Real, unedited finding: Flask 3.0.3 emits a DeprecationWarning for
# --- flask.__version__ on stderr. It is a WARNING, not an error - the
# --- request still returned 200 with the correct JSON body, confirmed
# --- above. Flask's own dev-server banner also warns it isn't meant for
# --- production, which is expected and fine for this homework demo. ---
```

### Image sizes for all Task 1 + Task 3 images

```console
root@ubuntu-hw:~# docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | grep -E "ms-app|ms-deploy"
ms-deploy-java:latest                                                                         286MB
ms-deploy-python:latest                                                                       112MB
ms-deploy-node:latest                                                                         234MB
ms-app:singlestage                                                                            468MB
ms-app:multistage                                                                             7.3MB
```

### Cleanup - stop and remove containers, keep the images

```console
root@ubuntu-hw:~# docker stop ms-app ms-deploy-node ms-deploy-python ms-deploy-java
ms-app
ms-deploy-node
ms-deploy-python
ms-deploy-java

root@ubuntu-hw:~# docker rm ms-app ms-deploy-node ms-deploy-python ms-deploy-java
ms-app
ms-deploy-node
ms-deploy-python
ms-deploy-java

root@ubuntu-hw:~# docker ps --filter "name=ms-"
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES

# --- No containers running - all four stopped and removed as required. ---

root@ubuntu-hw:~# docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | grep -E "REPOSITORY|ms-app|ms-deploy"
REPOSITORY:TAG                                                                                SIZE
ms-deploy-java:latest                                                                         286MB
ms-deploy-python:latest                                                                       112MB
ms-deploy-node:latest                                                                         234MB
ms-app:singlestage                                                                            468MB
ms-app:multistage                                                                             7.3MB

# --- Images kept as required, only the containers were removed. ---
```
