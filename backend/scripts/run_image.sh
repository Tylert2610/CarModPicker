#!/usr/bin/env bash
#
# Run one domain's image locally and hold the port open.
#
#   scripts/run_image.sh media
#   PORT=8081 scripts/run_image.sh users
#
# What this is for: proving an image actually starts, that its entrypoint binds
# the port the Lambda Web Adapter polls, and that `/health` answers without
# touching a database. It is not a substitute for running the application in
# development, which is what `docker-compose.yml` plus Root A is for.
#
# The container talks to whatever DynamoDB it is pointed at. With
# `docker compose up -d dynamodb` running, the default below reaches DynamoDB
# Local through the host gateway, so `/ready` answers 200 as well as `/health`.
# Without it, `/health` still answers 200 and `/ready` answers 503, which is the
# correct behaviour and is exactly why the adapter polls the first and not the
# second.
#
# Credentials are dummies on purpose. The point of the check is that the process
# starts and serves, and a domain that needed real AWS to answer `/health` would
# be a domain whose readiness check was wrong.

set -euo pipefail

DOMAIN="${1:-}"
TAG="${TAG:-local}"

# Which repository name to run from, matching `build_image.sh`'s default. This
# names the image on the host; it is not what the container runs as. The
# container is always given APP_ENVIRONMENT=test below, because this script
# points at DynamoDB Local with dummy credentials and running it as anything
# else would invite an image built for staging to be pointed at staging's data.
ENVIRONMENT="${ENVIRONMENT:-staging}"
IMAGE_REPO="${IMAGE_REPO:-carmodpicker-${ENVIRONMENT}/${DOMAIN}}"
IMAGE="${IMAGE:-${IMAGE_REPO}:${TAG}}"

# The host port. The container always listens on 8080, because that is what the
# adapter polls and what the base image sets PORT to.
HOST_PORT="${PORT:-8080}"

usage() {
    cat >&2 <<'USAGE'
usage: run_image.sh <domain>

  domain  one of identity, users, catalog, vehicles, build-lists, build-logs,
          moderation, media, admin

environment:
  PORT                   host port to publish on, default 8080
  TAG                    image tag to run, default "local"
  IMAGE                  full image reference, overriding repo and tag
  DYNAMODB_ENDPOINT_URL  default http://host.docker.internal:8001, which is
                         DynamoDB Local as docker-compose.yml publishes it
  DYNAMODB_TABLE_PREFIX  default carmodpicker-test

Build the image first:

  export CODEARTIFACT_AUTH_TOKEN="$(aws codeartifact get-authorization-token \
    --domain webbpulse --domain-owner 432410731887 \
    --region us-west-2 --query authorizationToken --output text)"
  scripts/build_image.sh media

Then, in another shell:

  curl -fsS localhost:8080/health
  curl -sS  localhost:8080/ready
USAGE
    exit 2
}

case "${DOMAIN}" in
    identity|users|catalog|vehicles|build-lists|build-logs|moderation|media|admin) ;;
    "") echo "error: no domain given." >&2; usage ;;
    *) echo "error: '${DOMAIN}' is not a domain." >&2; usage ;;
esac

DYNAMODB_ENDPOINT_URL="${DYNAMODB_ENDPOINT_URL:-http://host.docker.internal:8001}"
DYNAMODB_TABLE_PREFIX="${DYNAMODB_TABLE_PREFIX:-carmodpicker-test}"

echo "running ${IMAGE} on localhost:${HOST_PORT} (health: /health, readiness: /ready)"

# --add-host is what makes host.docker.internal resolve on Linux, where it is
# not built in the way it is on Docker Desktop.
exec docker run --rm -it \
    --add-host host.docker.internal:host-gateway \
    -p "${HOST_PORT}:8080" \
    -e APP_ENVIRONMENT=test \
    -e ENVIRONMENT=test \
    -e "DYNAMODB_TABLE_PREFIX=${DYNAMODB_TABLE_PREFIX}" \
    -e "DYNAMODB_ENDPOINT_URL=${DYNAMODB_ENDPOINT_URL}" \
    -e AWS_REGION=us-west-2 \
    -e AWS_DEFAULT_REGION=us-west-2 \
    -e AWS_ACCESS_KEY_ID=dummy \
    -e AWS_SECRET_ACCESS_KEY=dummy \
    -e SECRET_KEY=local-development-signing-key-not-a-real-one \
    -e RUN_STARTUP_TASKS=false \
    "${IMAGE}"
