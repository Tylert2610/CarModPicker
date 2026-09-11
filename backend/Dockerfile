# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=432410731887.dkr.ecr.us-west-2.amazonaws.com/webbpulse/python-lambda-base@sha256:b5298b4b773ad6c9e311057cf5d43f37ceb98f0367347d714c6817f250a5cef7

FROM ${BASE_IMAGE} AS builder

USER root

WORKDIR /build

COPY requirements-lambda.txt ./

ARG CODEARTIFACT_DOMAIN=webbpulse
ARG CODEARTIFACT_DOMAIN_OWNER=432410731887
ARG CODEARTIFACT_REPOSITORY=python
ARG AWS_REGION=us-west-2

RUN --mount=type=secret,id=codeartifact_token,required=true \
    set -eu; \
    token="$(cat /run/secrets/codeartifact_token)"; \
    PIP_INDEX_URL="https://aws:${token}@${CODEARTIFACT_DOMAIN}-${CODEARTIFACT_DOMAIN_OWNER}.d.codeartifact.${AWS_REGION}.amazonaws.com/pypi/${CODEARTIFACT_REPOSITORY}/simple/" \
    PIP_EXTRA_INDEX_URL="https://pypi.org/simple/" \
    pip install --no-cache-dir --target /deps -r requirements-lambda.txt

RUN find /deps -type d -name "__pycache__" -prune -exec rm -rf {} + \
    && find /deps -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

FROM ${BASE_IMAGE} AS runtime

USER root

ARG DOMAIN
RUN set -eu; \
    test -n "${DOMAIN}" || { \
        echo "DOMAIN build arg is required: one of identity, users, catalog," >&2; \
        echo "vehicles, build-lists, build-logs, moderation, media, admin." >&2; \
        echo "  docker buildx build --build-arg DOMAIN=media ..." >&2; \
        exit 1; \
    }; \
    case "${DOMAIN}" in \
        identity|users|catalog|vehicles|build-lists|build-logs|moderation|media|admin) ;; \
        *) \
            echo "DOMAIN=${DOMAIN} is not a domain. Expected one of identity, users," >&2; \
            echo "catalog, vehicles, build-lists, build-logs, moderation, media, admin." >&2; \
            exit 1 ;; \
    esac; \
    module="${DOMAIN%%-*}"; \
    rest="${DOMAIN#"${module}"}"; \
    case "${rest}" in -*) module="${module}_${rest#-}" ;; esac; \
    echo "app.entrypoints.${module}" > /etc/carmodpicker-entrypoint

COPY --from=builder /deps /var/task
COPY app/ /var/task/app/

RUN set -eu; \
    module="$(sed 's/^app\.entrypoints\.//' /etc/carmodpicker-entrypoint)"; \
    test -f "/var/task/app/entrypoints/${module}.py" || { \
        echo "DOMAIN=${DOMAIN} maps to app/entrypoints/${module}.py, which is not in the image." >&2; \
        exit 1; \
    }

ENV DOMAIN=${DOMAIN} \
    PYTHONPATH=/var/task \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AWS_LWA_PORT=8080 \
    PORT=8080 \
    AWS_LWA_ASYNC_INIT=true \
    AWS_LWA_READINESS_CHECK_PATH=/health \
    AWS_LWA_READINESS_CHECK_PROTOCOL=http \
    RUN_STARTUP_TASKS=false

WORKDIR /var/task

USER app

CMD ["sh", "-c", "exec python -m \"$(cat /etc/carmodpicker-entrypoint)\""]
