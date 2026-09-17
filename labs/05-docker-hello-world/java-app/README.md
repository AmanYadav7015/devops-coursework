# Java Hello World

A single-file HTTP server built on the JDK's own `com.sun.net.httpserver.HttpServer`, so the app needs
no Maven, no Gradle and no third-party dependency. The Dockerfile is multi-stage: a JDK image compiles
`HelloWorld.java`, and only the resulting `.class` file is copied into a smaller JRE image.

You do not need a JDK on your laptop -- the compile happens inside the build stage.

## Build

```bash
cd homework/05-docker-hello-world/java-app
docker build -t hw05-java .
```

## Run

```bash
docker run -d --name hw05-java -p 8080:8080 hw05-java
docker ps --filter name=hw05-java
```

## Verify

```bash
curl http://localhost:8080
```

```text
<h1>Hello World from Java</h1>
```

Or open <http://localhost:8080> in a browser.

## Clean up

```bash
docker rm -f hw05-java
```
