# The composition tool of the Cosmo router: the Cosmo CLI `wgc` 0.133.0 (Apache-2.0), installed once into the image so that two builds
# from the same inputs use the same version, and composing needs no network, no account and no token.
#
# - The base is pinned by the digest of its OCI image index, the same node:22-slim as the Rover image of the Apollo router (resolved on
#   2026-10-16 with `docker buildx imagetools inspect node:22-slim`). Tags move: resolve the digest again before changing the pin.
# - wgc collects anonymous usage data (PostHog) unless COSMO_TELEMETRY_DISABLED=true (or DO_NOT_TRACK=1) is set; both names were read in
#   cli/src/core/telemetry.ts at the tag wgc@0.133.0. The image sets the first one.
FROM node:22-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392
ENV COSMO_TELEMETRY_DISABLED=true NPM_CONFIG_UPDATE_NOTIFIER=false
RUN npm install --global --no-audit --no-fund wgc@0.133.0
# wgc asks the npm registry for a newer version before every command and fails without a network (`Failed to check for updates`, seen
# with `--network none` on 2026-10-18); the check is switched off, so composing runs offline.
ENV DISABLE_UPDATE_CHECK=true
WORKDIR /work
ENTRYPOINT ["wgc"]
