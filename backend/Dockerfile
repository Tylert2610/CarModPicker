# syntax=docker/dockerfile:1.7
#
# One Dockerfile, nine images. `DOMAIN` selects which entrypoint the image runs;
# everything else about the nine is identical, which is what keeps the
# dependency layer bit-identical across them and the storage cost flat across
# nine ECR repositories per environment rather than nine times one image.
#
# Build it with `scripts/build_image.sh <domain>`, which supplies the
# CodeArtifact secret and the platform. The raw form is:
#
#   docker buildx build \
#     --platform linux/arm64 \
#     --build-arg DOMAIN=media \
#     --secret id=codeartifact_token,env=CODEARTIFACT_AUTH_TOKEN \
#     -t carmodpicker/media:sha-<commit> backend/
#
# Five things about this file are load-bearing rather than stylistic, and each
# of them is a decision the split plan's section 2.5 or Portfolio's own images
# already paid for.
#
# **The base image is pinned by digest, not by tag.** The default below is the
# same shared `webbpulse/python-lambda-base` image the Portfolio functions build
# FROM, in the Artifacts account. It is a multi-architecture index carrying both
# amd64 and arm64, so `--platform` selects the right one and a build with no
# `--build-arg BASE_IMAGE` is reproducible. It already carries the Lambda Web
# Adapter at `/opt/extensions/lambda-adapter`, so this file must not copy the
# adapter again: a second copy over the same path is wasted layer bytes at best
# and a version skew between the two at worst.
#
# **The dependency set is `requirements-lambda.txt`, not `requirements.txt`.**
# `requirements.txt` is the development set and carries `pytest`, `moto`,
# `black`, `mypy`, `locust` and `curl_cffi`. `curl_cffi` in particular is the
# crawler tier's TLS impersonation library: it ships native libcurl-impersonate
# binaries, it is the largest native dependency in the tree, and it has no
# server-side caller. Installing the development set would put all of that in
# every one of the nine images. `requirements-lambda.txt` is the runtime pin set
# and is what `backend-deploy.yml` already builds the monolith's zip from, so
# this is the same dependency closure that runs in production today.
#
# **The CodeArtifact token is a BuildKit secret mount.** A token passed as `ARG`
# or `ENV` persists in `docker history` for anyone who can pull the image. The
# mount exists only for the life of the RUN line, and the index URL is assembled
# inside that line so the token never becomes a layer. The install works whether
# or not `requirements-lambda.txt` yet names `webbpulse`: with the CodeArtifact
# index as `PIP_INDEX_URL` and PyPI as an extra index, public pins resolve from
# CodeArtifact's upstream and the shared package resolves from the domain
# itself, so adopting the package later changes this file not at all.
#
# **The runtime stage copies the installed tree, not the builder.** Development
# and test dependencies are never installed here, so nothing in
# `requirements.txt` that is absent from `requirements-lambda.txt` can reach the
# image by accident.
#
# **`/health` is the readiness path for all nine.** CarModPicker's `/health` is
# a static dictionary and `/ready` is the one that calls `check_db_ready()`, so
# the adapter can poll a route rather than fall back to a TCP check. Portfolio
# needed the `tcp` fallback for one domain whose only `/health` read its
# database; the root routes here were written with this in mind and no domain
# needs it.
# ---------------------------------------------------------------------------

ARG BASE_IMAGE=432410731887.dkr.ecr.us-west-2.amazonaws.com/webbpulse/python-lambda-base@sha256:b5298b4b773ad6c9e311057cf5d43f37ceb98f0367347d714c6817f250a5cef7

# ---------------------------------------------------------------------------
# Builder: resolve and install the runtime dependency set into /deps.
#
# `--target` rather than a virtualenv, because the runtime stage puts the same
# directory on PYTHONPATH and Lambda's read-only filesystem makes an activated
# venv more machinery than the layout needs.
# ---------------------------------------------------------------------------
FROM ${BASE_IMAGE} AS builder

# The base image drops to the unprivileged `app` user (uid 1000), which is right
# for the runtime stage but wrong here: BuildKit mounts secrets root-owned with
# mode 0400, so reading /run/secrets/codeartifact_token fails with "Permission
# denied" as `app`, and pip cannot create /deps at the filesystem root either.
# Nothing from this stage's filesystem survives except what the runtime stage
# copies out of /deps, so building as root widens nothing at runtime.
USER root

WORKDIR /build

# Only the requirements file, so a change under app/ does not invalidate the
# dependency layer. requirements.txt is deliberately neither copied nor
# installed.
COPY requirements-lambda.txt ./

# The CodeArtifact index. `aws` is the literal username CodeArtifact expects;
# the password is the token. Assembled inside the RUN so neither the token nor
# the assembled URL is written to a layer or to pip.conf.
#
# PyPI stays as an extra index rather than being replaced. CodeArtifact's
# `python` repository proxies PyPI upstream, so the public pins would resolve
# through it either way, but keeping the extra index means a build still
# succeeds if a package has not yet been pulled through the proxy. The shared
# `webbpulse` package exists only in CodeArtifact, so it resolves from the
# first index whether or not this requirements file names it yet.
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

# Caches only. Stripping them here keeps the layer the runtime stage copies as
# small as the install allows, and __pycache__ written against the builder's
# paths is not reused at runtime anyway.
RUN find /deps -type d -name "__pycache__" -prune -exec rm -rf {} + \
    && find /deps -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

# ---------------------------------------------------------------------------
# Runtime: the base image, the installed dependencies, and app/.
# ---------------------------------------------------------------------------
FROM ${BASE_IMAGE} AS runtime

# The base image ends on its unprivileged `app` user, and a stage inherits that.
# The two RUNs below write `/etc/carmodpicker-entrypoint` and read `/var/task`,
# so this stage is root until the `USER app` at the end. Without this line the
# first RUN fails with "cannot create /etc/carmodpicker-entrypoint: Permission
# denied", which is what took down the first nine image builds.
USER root

# Which domain this image serves. There is no default on purpose: an image built
# without it would silently be some arbitrary domain's, and the nine
# repositories would stop meaning what their names say.
#
# The check also converts the domain name to its module name. Domain names carry
# hyphens because they name ECR repositories, functions and log groups;
# `app/entrypoints/` carries underscores because Python modules must. `identity`
# and `build-lists` differ only in that respect, and getting the mapping wrong
# is a delayed failure rather than an immediate one, so it is resolved here at
# build time rather than by a shell expansion at container start.
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
    # Hyphens to underscores. Shell parameter substitution rather than a pipe
    # to `tr`, so the RUN has no pipe whose exit status could be swallowed;
    # only `build-lists` and `build-logs` actually contain a hyphen.
    module="${DOMAIN%%-*}"; \
    rest="${DOMAIN#"${module}"}"; \
    case "${rest}" in -*) module="${module}_${rest#-}" ;; esac; \
    echo "app.entrypoints.${module}" > /etc/carmodpicker-entrypoint

# Dependencies first, application second: app/ changes on every commit and the
# dependency layer changes only when requirements-lambda.txt does.
COPY --from=builder /deps /var/task
COPY app/ /var/task/app/

# The module assertion, after app/ is in place. Import is not attempted here,
# because importing the entrypoint would need the settings and AWS environment
# a build does not have; the file's presence is what is checked, and
# `build_app` importing cleanly is what `backend/tests/entrypoints/` proves.
RUN set -eu; \
    module="$(sed 's/^app\.entrypoints\.//' /etc/carmodpicker-entrypoint)"; \
    test -f "/var/task/app/entrypoints/${module}.py" || { \
        echo "DOMAIN=${DOMAIN} maps to app/entrypoints/${module}.py, which is not in the image." >&2; \
        exit 1; \
    }

ENV DOMAIN=${DOMAIN} \
    PYTHONPATH=/var/task \
    # Python buffers stdout when it is not a terminal, so without this a log
    # line can sit in the buffer while the execution environment is frozen
    # between invokes and arrive attributed to a later request.
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # The port the adapter polls. The base image already sets both of these to
    # 8080; they are repeated because `Settings.PORT` defaults to 8000 and it is
    # the `PORT` environment variable that overrides it. An entrypoint binding
    # 8000 while the adapter polls 8080 presents as the readiness check never
    # passing, with no application logs at all.
    AWS_LWA_PORT=8080 \
    PORT=8080 \
    # Moves slow imports into Lambda's ten second init window rather than
    # charging them to the first invoke. Nine cold paths instead of one makes
    # this matter more than it did on the monolith.
    AWS_LWA_ASYNC_INIT=true \
    # `/health` is a static dictionary in `add_root_routes`; `/ready` is the one
    # that calls `check_db_ready()`. Polling `/ready` would put a DynamoDB read
    # in front of every cold start and would fail a function to start whenever
    # its tables were briefly unavailable.
    AWS_LWA_READINESS_CHECK_PATH=/health \
    AWS_LWA_READINESS_CHECK_PROTOCOL=http \
    # The lifespan startup work seeds car generations and sweeps orphan jobs.
    # One process per domain doing that on every cold start is nine times the
    # work and none of it belongs in a request path; the seed job owns it.
    RUN_STARTUP_TASKS=false

WORKDIR /var/task

# Back to the base image's unprivileged user for the runtime stage. The COPYs
# above land root-owned and world-readable, which is what a read-only Lambda
# filesystem wants.
USER app

# `sh -c` rather than an exec-form CMD with the module inlined, because CMD does
# not expand a build-time ARG. The module name is read from the file the check
# above wrote, so the hyphen-to-underscore mapping happens once at build time
# rather than on every container start. `exec` replaces the shell so the Python
# process is PID 1 and receives Lambda's signals directly.
CMD ["sh", "-c", "exec python -m \"$(cat /etc/carmodpicker-entrypoint)\""]
