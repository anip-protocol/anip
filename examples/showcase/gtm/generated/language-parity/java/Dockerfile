FROM maven:3.9-eclipse-temurin-17

WORKDIR /repo

COPY packages/java /repo/packages/java
COPY examples/showcase/gtm/generated/language-parity/java /repo/examples/showcase/gtm/generated/language-parity/java

WORKDIR /repo/examples/showcase/gtm/generated/language-parity/java

RUN mvn -q test package

EXPOSE 4100

CMD ["java", "-jar", "target/gtm-operator-contract-20260512235040-0.1.0.jar", "--server.port=4100"]
