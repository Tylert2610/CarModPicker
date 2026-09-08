#!/usr/bin/env bash
#
# Build one domain's container image.
#
#   scripts/build_image.sh media
#   scripts/build_image.sh build-lists sha-1a2b3c4
#   PLATFORM=linux/amd64 scripts/build_image.sh users
#
# Deliberately thin. It exists so the two things that are easy to get wrong and
# expensive to get wrong are in one place rather than in every caller:
#
#   - the CodeArtifact token reaches pip as a BuildKit secret and never as a
#     build argument, where it would persist in `docker history`; and
#   - the platform is the one the domain functions are configured for, so a
#     hand-built image cannot quietly be the wrong architecture.
#
# Everything else is a pass-through. The deploy workflow in the plan's row 12
# wraps the org `container-image.yml` rather than calling this, so anything
# genuinely policy-shaped belongs in the Dockerfile, where both paths read it.

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DOMAIN="${1:-}"
TAG="${2:-local}"

# Defaults match `terraform/ecr.tf` and the CodeArtifact domain the shared
# package is published to. Override any of them from the environment.
#
# The repository name is `carmodpicker-<env>/<domain>`, because the ECR module
# takes `local.prefix` as its `name_prefix`; the slash namespaces one
# environment's nine repositories together in the console.
PLATFORM="${PLATFORM:-linux/arm64}"
ENVIRONMENT="${ENVIRONMENT:-staging}"
IMAGE_REPO="${IMAGE_REPO:-carmodpicker-${ENVIRONMENT}/${DOMAIN}}"
CODEARTIFACT_DOMAIN="${CODEARTIFACT_DOMAIN:-webbpulse}"
CODEARTIFACT_DOMAIN_OWNER="${CODEARTIFACT_DOMAIN_OWNER:-432410731887}"
CODEARTIFACT_REPOSITORY="${CODEARTIFACT_REPOSITORY:-python}"
AWS_REGION="${AWS_REGION:-us-west-2}"

usage() {
    cat >&2 <<'USAGE'
usage: build_image.sh <domain> [tag]

  domain  one of identity, users, catalog, vehicles, build-lists, build-logs,
          moderation, media, ingestion
  tag     image tag, default "local". CI passes sha-<commit>, which is what the
          ECR repositories' immutable tag prefix expects.

environment:
  CODEARTIFACT_AUTH_TOKEN   required. Mint one with:
      export CODEARTIFACT_AUTH_TOKEN="$(aws codeartifact get-authorization-token \
        --domain webbpulse --domain-owner 432410731887 \
        --region us-west-2 --query authorizationToken --output text)"
  PLATFORM                  default linux/arm64, matching the architectures the
                            plan's section 3.3 gives the domain functions
  ENVIRONMENT               default staging, used to build the default repo name
  IMAGE_REPO                default carmodpicker-<environment>/<domain>
  BASE_IMAGE                default is the digest pinned in the Dockerfile
  PUSH                      set to 1 to push instead of loading locally

The base image lives in the Artifacts account, so pulling it needs an ECR login
against that registry even when pushing somewhere else:

  aws ecr get-login-password --region us-west-2 \
    | docker login --username AWS --password-stdin \
      432410731887.dkr.ecr.us-west-2.amazonaws.com
USAGE
    exit 2
}

case "${DOMAIN}" in
    identity|users|catalog|vehicles|build-lists|build-logs|moderation|media|ingestion) ;;
    "") echo "error: no domain given." >&2; usage ;;
    *) echo "error: '${DOMAIN}' is not a domain." >&2; usage ;;
esac

if [[ -z "${CODEARTIFACT_AUTH_TOKEN:-}" ]]; then
    echo "error: CODEARTIFACT_AUTH_TOKEN is not set." >&2
    echo "The dependency install resolves through CodeArtifact, which needs a token." >&2
    usage
fi

IMAGE="${IMAGE_REPO}:${TAG}"

# --load leaves the image in the local daemon, which is what a software engineer
# wants and what `docker run` needs. CI sets PUSH=1. buildx will not both load
# and push in one invocation for a single-platform build, hence the either or
# rather than a list.
if [[ "${PUSH:-0}" == "1" ]]; then
    OUTPUT_ARGS=(--push)
else
    OUTPUT_ARGS=(--load)
fi

# Single platform on purpose. Lambda rejects an OCI image index, so a domain
# image must be one architecture; only the base image this builds FROM is a
# multi-architecture manifest.
BUILD_ARGS=(
    --platform "${PLATFORM}"
    --build-arg "DOMAIN=${DOMAIN}"
    --build-arg "CODEARTIFACT_DOMAIN=${CODEARTIFACT_DOMAIN}"
    --build-arg "CODEARTIFACT_DOMAIN_OWNER=${CODEARTIFACT_DOMAIN_OWNER}"
    --build-arg "CODEARTIFACT_REPOSITORY=${CODEARTIFACT_REPOSITORY}"
    --build-arg "AWS_REGION=${AWS_REGION}"
    --secret "id=codeartifact_token,env=CODEARTIFACT_AUTH_TOKEN"
    --tag "${IMAGE}"
)

# Only when overridden, so an unset BASE_IMAGE takes the Dockerfile's pinned
# digest rather than an empty string.
if [[ -n "${BASE_IMAGE:-}" ]]; then
    BUILD_ARGS+=(--build-arg "BASE_IMAGE=${BASE_IMAGE}")
fi

echo "building ${IMAGE} (domain=${DOMAIN}, platform=${PLATFORM})"

docker buildx build "${BUILD_ARGS[@]}" "${OUTPUT_ARGS[@]}" "${BACKEND_DIR}"

echo "built ${IMAGE}"
