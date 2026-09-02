# Java Hello World

**Assignment requirements** (verbatim from `DevOps Homework.docx`):

> - Create a separate folder: `java-app`
> - Add the application code.
> - Create a Dockerfile.
> - Build the Docker image.
> - Run the application using Docker.
> - Verify that Hello World is displayed on a webpage.

*Built and run on macOS with Docker Desktop, from `docker-fundamentals/java-app/`.*

[← Back to Docker Fundamentals](../README.md)

---

## What's here

- `src/HelloWorld.java` — plain Java using only the JDK standard library
  (`com.sun.net.httpserver.HttpServer`). No Maven, no Gradle, no external
  dependencies — compiled directly with `javac`. It serves a small HTML page
  with "Hello World" and the container's hostname.
- `Dockerfile` — a **multi-stage build**: a JDK image compiles the source, and a
  much smaller JRE-only image runs the compiled `.class` files.

## Dockerfile, line by line

```dockerfile
# ---- Stage 1: build ----
FROM eclipse-temurin:21-jdk-alpine AS build
WORKDIR /build
COPY src/HelloWorld.java .
RUN javac HelloWorld.java

# ---- Stage 2: runtime ----
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /build/*.class .
EXPOSE 8080
CMD ["java", "HelloWorld"]
```

| Line | What it does |
|---|---|
| `FROM eclipse-temurin:21-jdk-alpine AS build` | First stage, named `build`. Uses a full JDK image (includes `javac`) purely to compile the source — this stage is discarded from the final image. |
| `WORKDIR /build` | Working directory for the build stage. |
| `COPY src/HelloWorld.java .` | Copies the single Java source file in. |
| `RUN javac HelloWorld.java` | Compiles it with the plain JDK compiler — no build tool needed for one file. |
| `FROM eclipse-temurin:21-jre-alpine` | Second stage: a **JRE-only** image (no compiler, no build tools) — much smaller than the JDK image. This is the image that actually ships. |
| `WORKDIR /app` | Working directory for the runtime stage. |
| `COPY --from=build /build/*.class .` | Copies **all** compiled `.class` files from the `build` stage into the final image (see the bug below for why the glob matters). |
| `EXPOSE 8080` | Documents the port the app listens on. |
| `CMD ["java", "HelloWorld"]` | Runs the compiled class with the JRE. |

## Build & run

```bash
docker build -t df-java:1.0 .
docker run -d --name df-java -p 18083:8080 df-java:1.0
curl -s http://localhost:18083
```

## What actually happened

**Real bug found and fixed.** The first version of the Dockerfile copied only the
named file: `COPY --from=build /build/HelloWorld.class .`. The build succeeded, the
image built, but the container immediately exited:

```
Exception in thread "main" java.lang.NoClassDefFoundError: HelloWorld$HelloHandler
	at HelloWorld.main(HelloWorld.java:23)
Caused by: java.lang.ClassNotFoundException: HelloWorld$HelloHandler
```

Root cause: `javac` compiles **one `.class` file per class**, including nested
classes. `HelloWorld.java` defines a nested static class `HelloHandler` (the HTTP
handler), so `javac` produced *two* files: `HelloWorld.class` and
`HelloWorld$HelloHandler.class`. The Dockerfile only copied the first one into the
runtime stage, so the JVM could load the entry class but not the handler it
referenced at runtime. Fixed by copying the whole set with a glob:
`COPY --from=build /build/*.class .`, then rebuilding. See
`transcripts/docker-a.txt` and `transcripts/docker-c.txt` for the failing run and
the fix.

After the fix, `curl -s http://localhost:18083` returned HTML containing
`<h1>Hello World</h1>`, and `curl -I` returned `HTTP/1.1 200 OK`.

Final image: **286MB disk usage / 73.4MB content size** — by far the biggest of the
six, even with a multi-stage build and Alpine base. See the topic
[README](../README.md) for why (short version: the JRE itself, even
`-alpine`/`eclipse-temurin`, is a much larger runtime than Node's, Python's, or a
static web server's).
