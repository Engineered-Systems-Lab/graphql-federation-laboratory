# The mapping adapter image: the executable jar, the immutable mapping releases and a Java 21 runtime, nothing else (no sources, no
# tests, no credentials). The adapter has no database and makes no outbound call.
#
# The build context is the federation/ folder (the parent pom, the shared library, the adapters and the mapping releases), so build with
#   docker build -f adapters/mapping/Dockerfile .      (from federation/; compose does this)
# The build stage runs the offline unit and integration tests (`mvn verify`), among them the hash of every release file against its
# manifest: an image never exists for code or data whose tests fail. No JDK or Maven is needed on the machine.
#
# Both bases are pinned by the digest of their OCI image index, the same two the Assets adapter uses. The digests were resolved on
# 2026-10-16 with `docker buildx imagetools inspect <tag>`; they are the digests of 2026-10-15, so the tags had not moved in a day.
# Tags move: resolve the digests again before changing a pin, and record the date here and in the README.
#   maven:3.9-eclipse-temurin-21   Maven 3.9 with Temurin 21 (build)
#   eclipse-temurin:21-jre         Temurin 21 JRE (runtime)
FROM maven:3.9-eclipse-temurin-21@sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320 AS build
WORKDIR /build
COPY pom.xml ./
COPY common ./common
COPY adapters ./adapters
COPY mapping-releases ./mapping-releases
RUN --mount=type=cache,target=/root/.m2 mvn -B -ntp -pl adapters/mapping -am verify

FROM eclipse-temurin:21-jre@sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef
WORKDIR /app
COPY --from=build /build/adapters/mapping/target/federation-mapping-adapter-1.0.0.jar ./adapter.jar
COPY mapping-releases ./mapping-releases
ENV ADAPTER_BIND_HOST=0.0.0.0 ADAPTER_PORT=8190 MAPPING_RELEASES_DIR=/app/mapping-releases
USER 10001:10001
EXPOSE 8190
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=70", "-jar", "/app/adapter.jar"]
