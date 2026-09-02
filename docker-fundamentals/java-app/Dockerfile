# ---- Stage 1: build ----
# JDK image (includes javac) used only to compile the source.
# This stage is discarded from the final image, so its size doesn't matter.
FROM eclipse-temurin:21-jdk-alpine AS build

WORKDIR /build

# Copy source and compile with plain javac - no Maven/Gradle needed
COPY src/HelloWorld.java .
RUN javac HelloWorld.java

# ---- Stage 2: runtime ----
# Much smaller JRE-only image (no compiler, no build tools) for actually
# running the app. This is what keeps the final image small.
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# Copy all compiled .class files from the build stage.
# javac produces one file per class, including HelloWorld$HelloHandler.class
# for the nested static handler class - copying only HelloWorld.class caused
# a NoClassDefFoundError at runtime, so we copy the whole set with a glob.
COPY --from=build /build/*.class .

EXPOSE 8080

CMD ["java", "HelloWorld"]
