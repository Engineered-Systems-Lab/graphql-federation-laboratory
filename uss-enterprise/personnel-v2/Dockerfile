FROM maven:3.9.11-eclipse-temurin-17@sha256:e4a7ace3dc0d645ed97f8d9ad0b0d3f0b14fa8d150138f27f116d7105a639b82 AS build
WORKDIR /build
COPY pom.xml ./
COPY contracts ./contracts
COPY datasets ./datasets
COPY src ./src
RUN mvn -B -ntp verify

FROM eclipse-temurin:17-jre-jammy@sha256:97137382c6f0c30427d9b7c44ad8b2d55ac823b0768c171d81a643ed219023c5
WORKDIR /app
COPY --from=build /build/target/personnel-v2-2.0.0.jar ./service.jar
COPY --from=build /build/target/lib ./lib
ENV PERSONNEL_BIND_HOST=0.0.0.0 PERSONNEL_PORT=8082 PERSONNEL_DATASET_VERSION=personnel-v2-small-002 PERSONNEL_FAILURE_PROFILE=normal
USER 10001:10001
EXPOSE 8082
ENTRYPOINT ["java", "-Dcom.sun.org.apache.xerces.internal.impl.dv.xs.useCodePointCountForStringLength=true", "-jar", "/app/service.jar"]
