FROM eclipse-temurin:21-jdk AS builder

WORKDIR /build

COPY HelloWorld.java .

RUN javac HelloWorld.java

FROM eclipse-temurin:21-jre

WORKDIR /app

COPY --from=builder /build/HelloWorld.class .

EXPOSE 8080

CMD ["java", "HelloWorld"]
