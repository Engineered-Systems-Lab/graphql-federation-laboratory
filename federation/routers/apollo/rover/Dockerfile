# The composition tool of the Apollo adapter: Rover 1.0.0 with the composition plugin `supergraph` v2.9.3 already inside the image,
# so that composing needs no network and two builds from the same inputs use the same plugin.
#
# THE ELv2 LICENSE: Rover's composition plugin is under the Elastic License 2.0 and Rover asks for acceptance before it downloads or
# runs it. This file accepts nothing on anyone's behalf: the first RUN stops the build unless the person who builds it accepts the
# license on purpose, by passing --build-arg APOLLO_ELV2_LICENSE=accept (compose_supergraph.py builds with that argument only after
# its own environment variable of the same name says `accept`, and refuses otherwise). Only after that proof does the download RUN
# repeat the acceptance for the plugin. The lead developer accepted it for the federation_router_apollo Job on 2026-10-16.
#
# - node:22-slim has no CA certificates, and Rover then fails ("No CA certificates were loaded"). The Temurin image carries the
#   system bundle, so the bundle is copied from it (federation experiment 1) instead of installing a package.
# - The plugin is downloaded once, here, by composing a tiny two-line graph; afterwards it is cached in /root/.rover of the image.
# - Rover's telemetry is switched off.
#
# Both bases are pinned by the digest of their OCI image index, resolved on 2026-10-16 with `docker buildx imagetools inspect <tag>`.
# Tags move: resolve the digests again before changing a pin, and record the date here and in the README.
#   node:22-slim            Node 22 (to run npm)
#   eclipse-temurin:21-jre  only for /etc/ssl/certs/ca-certificates.crt
FROM eclipse-temurin:21-jre@sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef AS certificates

FROM node:22-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392
ARG APOLLO_ELV2_LICENSE
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt APOLLO_TELEMETRY_DISABLED=1 NPM_CONFIG_UPDATE_NOTIFIER=false
COPY --from=certificates /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
RUN test "$APOLLO_ELV2_LICENSE" = "accept" || { echo "Refusing to build: Rover's composition plugin is under the Elastic License 2.0; pass --build-arg APOLLO_ELV2_LICENSE=accept to accept it" >&2; exit 1; }
RUN npm install --global --no-audit --no-fund @apollo/rover@1.0.0
COPY seed.graphql /seed/seed.graphql
COPY seed.yaml /seed/seed.yaml
RUN APOLLO_ELV2_LICENSE=accept APOLLO_ROVER_ALLOW_AUTOMATIC_DOWNLOAD=true rover supergraph compose --config /seed/seed.yaml --output /tmp/seed-supergraph.graphql \
    && rm -rf /seed /tmp/seed-supergraph.graphql
WORKDIR /work
ENTRYPOINT ["rover"]
