# The Assets read service image: the service code, the schema, the load script, the contract the load script checks
# and dataset release 1.1, and nothing else (no tests, no credentials).
#
# The base is python:3.13-slim-bookworm, pinned by the digest of its OCI image index. The digest was resolved on
# 2026-10-15 with `docker buildx imagetools inspect python:3.13-slim-bookworm`. Tags move: resolve the digest again
# before changing the pin, and record the date here and in the README.
FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# The pinned dependencies first, so that a change of code does not reinstall them. The wheels carry their own libpq.
COPY service/requirements.txt ./service/requirements.txt
RUN pip install -r service/requirements.txt
COPY service/*.py ./service/
COPY schema/schema.sql ./schema/schema.sql
COPY contracts/assets-v1.1.openapi.json ./contracts/assets-v1.1.openapi.json
COPY datasets/releases/1.1 ./datasets/releases/1.1
ENV ASSETS_HOST=0.0.0.0 ASSETS_PORT=8084
USER 10001:10001
EXPOSE 8084
CMD ["python", "-B", "/app/service/assets_service.py"]
