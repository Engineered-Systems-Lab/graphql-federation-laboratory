# The Assets adapter image: the executable jar and a Java 21 runtime, nothing else (no sources, no tests, no credentials).
#
# The build context is the federation/ folder (the parent pom, the shared library and the adapter), so build with
#   docker build -f adapters/assets/Dockerfile .      (from federation/; compose does this)
# The build stage runs the offline unit and integration tests (`mvn verify`): an image never exists for code whose tests fail.
# No JDK or Maven is needed on the machine.
# `COPY adapters` takes the pom and the sources of every adapter, because the parent pom lists every module; only this one is built.
#
# Both bases are pinned by the digest of their OCI image index. The digests were resolved on 2026-10-16 with
# `docker buildx imagetools inspect <tag>`; they are the digests of 2026-10-15, so the tags had not moved in a day.
# Tags move: resolve the digests again before changing a pin, and record the date here and in the README.
#   maven:3.9-eclipse-temurin-21   Maven 3.9 with Temurin 21 (build)
#   eclipse-temurin:21-jre         Temurin 21 JRE (runtime)
FROM maven:3.9-eclipse-temurin-21@sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320 AS build
WORKDIR /build
COPY pom.xml ./
COPY common ./common
COPY adapters ./adapters
RUN --mount=type=cache,target=/root/.m2 mvn -B -ntp -pl adapters/assets -am verify

FROM eclipse-temurin:21-jre@sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef
WORKDIR /app
COPY --from=build /build/adapters/assets/target/federation-assets-adapter-1.0.0.jar ./adapter.jar
ENV ADAPTER_BIND_HOST=0.0.0.0 ADAPTER_PORT=8184
USER 10001:10001
EXPOSE 8184
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=70", "-jar", "/app/adapter.jar"]
