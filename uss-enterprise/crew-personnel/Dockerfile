FROM maven:3.9.11-eclipse-temurin-17@sha256:e4a7ace3dc0d645ed97f8d9ad0b0d3f0b14fa8d150138f27f116d7105a639b82 AS build
WORKDIR /build
COPY pom.xml ./
COPY contracts ./contracts
COPY fixtures ./fixtures
COPY datasets/released/crew-v1-large-003 ./datasets/released/crew-v1-large-003
COPY src ./src
RUN mvn -B -ntp verify

FROM eclipse-temurin:17-jre-jammy@sha256:97137382c6f0c30427d9b7c44ad8b2d55ac823b0768c171d81a643ed219023c5
WORKDIR /app
COPY --from=build /build/target/crew-personnel-1.0.0.jar ./service.jar
COPY --from=build /build/target/lib ./lib
ENV CREW_BIND_HOST=0.0.0.0 CREW_PORT=8081 CREW_DATASET_VERSION=crew-v1-small-002 CREW_FAILURE_PROFILE=normal
USER 10001:10001
EXPOSE 8081
ENTRYPOINT ["java", "-Dcom.sun.org.apache.xerces.internal.impl.dv.xs.useCodePointCountForStringLength=true", "-jar", "/app/service.jar"]
