# The Missions adapter image: the executable jar and a Java 21 runtime, nothing else (no sources, no tests, no credentials).
#
# The build context is the REPOSITORY ROOT, not federation/: the offline tests read the real Missions contract fixtures and the
# six pages of the released dataset 1.2 (uss-enterprise/missions), and a copy of those files would be a second source. Build with
#   docker build -f federation/adapters/missions/Dockerfile .      (from the repository root; compose does this)
# Dockerfile.dockerignore keeps the context to the federation poms and sources, the fixtures and the six pages of the released list.
# The build stage runs the offline unit and integration tests (`mvn verify`): an image never exists for code whose tests fail.
# No JDK or Maven is needed on the machine.
#
# Both bases are pinned by the digest of their OCI image index; they are the digests of the Assets adapter image, resolved on
# 2026-10-16 with `docker buildx imagetools inspect <tag>` (the digests of 2026-10-15: the tags had not moved in a day).
# Tags move: resolve the digests again before changing a pin, and record the date here and in the README.
#   maven:3.9-eclipse-temurin-21   Maven 3.9 with Temurin 21 (build)
#   eclipse-temurin:21-jre         Temurin 21 JRE (runtime)
FROM maven:3.9-eclipse-temurin-21@sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320 AS build
WORKDIR /build
COPY federation ./federation
COPY uss-enterprise/missions/fixtures ./uss-enterprise/missions/fixtures
COPY uss-enterprise/missions/datasets/releases/1.2 ./uss-enterprise/missions/datasets/releases/1.2
WORKDIR /build/federation
RUN --mount=type=cache,target=/root/.m2 mvn -B -ntp -pl adapters/missions -am verify

FROM eclipse-temurin:21-jre@sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef
WORKDIR /app
COPY --from=build /build/federation/adapters/missions/target/federation-missions-adapter-1.0.0.jar ./adapter.jar
ENV ADAPTER_BIND_HOST=0.0.0.0 ADAPTER_PORT=8183
USER 10001:10001
EXPOSE 8183
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=70", "-jar", "/app/adapter.jar"]
