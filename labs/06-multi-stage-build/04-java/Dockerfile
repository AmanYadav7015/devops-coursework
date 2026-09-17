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
