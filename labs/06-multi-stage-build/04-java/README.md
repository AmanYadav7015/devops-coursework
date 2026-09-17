# 04-java — Java multi-stage build

Plain Java 21 HTTP server (`com.sun.net.httpserver`, no external dependencies) on **container port
8080**, published on host port 8093. Returns `Hello World from Java multi-stage build`.

## The multi-stage pattern: compile on a JDK, run on a JRE

```text
FROM eclipse-temurin:21-jdk AS builder
WORKDIR /build
COPY src ./src
RUN mkdir -p out \
    && javac -d out src/HelloServer.java \
    && jar --create --file app.jar --main-class HelloServer -C out .

FROM eclipse-temurin:21-jre-alpine AS runtime
WORKDIR /app
COPY --from=builder /build/app.jar ./app.jar
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
```

Java draws the cleanest line of the three languages, because the JDK and the JRE are separate products.
The **JDK** contains `javac`, `jar`, `jlink`, `jdb` and the rest of the development toolchain; the
**JRE** contains only what is needed to execute bytecode. The builder stage compiles `HelloServer.java`
and packages the classes into `app.jar`; the runtime stage takes that one file and nothing else.

Verification, showing that the compiler and the source code are genuinely absent:

```bash
docker run --rm hw06-java:multi  sh -c 'ls -1 /app; echo "---"; which javac || echo "javac: not found"'
docker run --rm hw06-java:single sh -c 'ls -1 /app; echo "---"; which javac'
```

```text
app.jar
---
javac: not found

app.jar
out
src
---
/opt/java/openjdk/bin/javac
```

The multi-stage image contains exactly one file. The single-stage image ships your source tree, the
compiled `out/` directory and a working compiler into production.

## Build, run, verify

```bash
docker build -t hw06-java:multi  -f Dockerfile .
docker build -t hw06-java:single -f Dockerfile.single-stage .
docker run -d --name hw06-java -p 8093:8080 hw06-java:multi
docker logs hw06-java
curl -s http://localhost:8093/
```

```text
java app listening on port 8080
Hello World from Java multi-stage build
```

## Measured size

| Build | Base image | Disk usage | Pull size |
|---|---|---|---|
| `hw06-java:single` | `eclipse-temurin:21-jdk` | 744 MB | 221 MB |
| `hw06-java:multi` | `eclipse-temurin:21-jre-alpine` | 286 MB | 73.4 MB |

**Saving: 458 MB on disk (−61.6%), 148 MB per pull (−66.8%).**

The percentage is lower than Node or Python because a JRE is irreducibly large — you cannot run Java
without one. The absolute saving is still 458 MB on every node that pulls this image, and the security
win (no compiler, no source) is the same.
