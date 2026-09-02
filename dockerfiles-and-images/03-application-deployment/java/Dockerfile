# Multi-stage build for the Java deployment demo.
#
# Stage 1 "builder": a full JDK + Maven image resolves dependencies from
# Maven Central and compiles/packages a shaded (fat) jar - large, and not
# needed at runtime. Stage 2 copies only the built jar into a JRE-only
# image (no compiler, no Maven, no dependency cache).

# ---- Stage 1: builder ----
FROM maven:3.9-eclipse-temurin-21-alpine AS builder
WORKDIR /build
COPY pom.xml .
COPY src ./src
RUN mvn -B -q -DskipTests package

# ---- Stage 2: runtime ----
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=builder /build/target/ms-deploy-java.jar ./app.jar

EXPOSE 8080
RUN addgroup -S app && adduser -S app -G app
USER app

CMD ["java", "-jar", "app.jar"]
