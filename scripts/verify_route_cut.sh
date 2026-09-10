#!/usr/bin/env bash
#
# Verify that one domain's routes were actually cut over to that domain's
# function, rather than resolving to some other route key or to no route at all.
#
# Section 6.3 of docs/migration/split-plan.md, "Verifying a flip". Each cut in
# section 3.5 moves a set of route keys onto a domain function, and the failure
# this script exists to catch is the quiet one: a cut that applies cleanly,
# answers normally, and changes nothing, because the route key did not match. A
# status code alone cannot tell that apart from a working cut.
#
# What a miss looks like changed in row 32. While the monolith was on $default a
# missed key fell through to it: the request was answered correctly by the wrong
# function, and this script reported routeKey $default. Row 32 retired the
# monolith and set default_integration = null, so there is no $default route any
# more and a missed key now 404s at the gateway. The $default branch below is
# kept because an estate part way through the migration, or a stage restored
# from before row 32, can still produce it.
#
#   scripts/verify_route_cut.sh <env> <domain>
#
#     env      staging or production
#     domain   one of the nine names in local.lambda_domain_names
#
# How it decides
# --------------
# The API Gateway access log carries `routeKey`, and section 6.3 names it as the
# check: before a cut every entry for the prefix reads "$default"; after it, they
# read the explicit route key. That is a property of the gateway rather than of
# the application, so it is true whichever image the function is running, and it
# distinguishes the two outcomes that look identical over HTTP.
#
# CarModPicker has no per-response domain header. Portfolio's equivalent script
# reads X-WebbPulse-Domain, which its `app/core/middleware.py` stamps on every
# response; nothing in this backend sets one, and adding it is a backend change
# rather than a routing one. So the access log is the primary signal here, not
# the cross-check it is in Portfolio. If a header is added later, prefer it: it
# is synchronous and needs no CloudWatch read.
#
# The flow per path is therefore:
#
#   1. Send one request with a correlation marker in the user agent.
#   2. Read the access log for the entry carrying that marker.
#   3. Assert its routeKey is this domain's explicit key, not "$default".
#
# The marker works because terraform/apigateway.tf takes the http-api module's
# default access_log_format, which carries `userAgent` alongside `path` and
# `routeKey`. If that format is ever narrowed to drop `userAgent`, the filter
# pattern here stops matching and every path reports as unlogged; widen the
# format again rather than loosening the pattern to match on the path, which
# would pick up unrelated traffic to the same prefix.
#
# Delivery is per log stream, so two probes a second apart can arrive tens of
# seconds apart. Step 2 therefore polls until every expected path has appeared,
# accumulating results across polls, rather than reading a single response once.
#
# A second, independent check confirms the function itself is answering: the
# domain function's log group gets an invocation in the same window. Without it
# a routeKey could name the right key while the integration pointed somewhere
# unexpected.
#
# The staging access gate
# -----------------------
# Behind the gate the API host answers only an OPTIONS preflight, a request
# carrying the origin-verify header, or one carrying valid CloudFront signed
# cookies. A bare curl gets 401 from the gate's authorizer, which would read
# here as a failed cut when it is really a missing credential.
#
# Nothing is embedded in this file. Supply one of:
#
#   CARMODPICKER_ORIGIN_VERIFY   the origin-verify header value. What CI uses.
#   CARMODPICKER_GATE_COOKIE     a Cookie header value, for a browser session.
#
# Neither is needed against an environment with no gate. To read the header
# value yourself, with credentials that allow it:
#
#   export CARMODPICKER_ORIGIN_VERIFY=$(aws ssm get-parameter --with-decryption \
#     --name /carmodpicker-staging/access-gate/origin-verify \
#     --query Parameter.Value --output text)
#
# In CI, mask it with ::add-mask:: before it can reach a log.
#
# If no gate credential is available at all, set CARMODPICKER_INVOKE_FALLBACK=1.
# That skips the HTTP leg entirely and invokes the domain function directly with
# a synthesised HTTP API v2 event, the same probe deploy-backend.yml's
# smoke-domains job uses. It proves the function serves the path; it cannot
# prove the gateway routes to it, so it is a fallback and says so.
#
# Override the host with CARMODPICKER_API_BASE_URL when the environment is not
# on its custom domain, for example a staging profile serving on the execute-api
# hostname.

set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: scripts/verify_route_cut.sh <env> <domain>

  env      staging | production
  domain   media | build-logs | moderation | vehicles | admin
           | build-lists | identity | catalog | users

Environment:
  CARMODPICKER_ORIGIN_VERIFY   origin-verify header value for the staging gate
  CARMODPICKER_GATE_COOKIE     Cookie header value, as an alternative
  CARMODPICKER_INVOKE_FALLBACK set to 1 to skip HTTP and invoke the function
  CARMODPICKER_API_BASE_URL    override the API base URL entirely
  CARMODPICKER_CURL_TIMEOUT    per request timeout in seconds (default 20)
  CARMODPICKER_RETRIES         attempts per path (default 5)
  CARMODPICKER_LOG_WAIT        seconds to wait for the access log (default 120)
USAGE
  exit 2
}

[ $# -eq 2 ] || usage

ENV_NAME=$1
DOMAIN=$2

case "$ENV_NAME" in
staging | production) ;;
*)
  echo "Unknown environment: $ENV_NAME" >&2
  usage
  ;;
esac

# The path prefixes each cut moves, kept in the same order as section 3.5's
# table and as local.lambda_domain_path_prefixes in terraform/apigateway.tf. A
# prefix listed here must appear there for that domain, or this script will
# correctly report it as not cut over.
#
# `media` from row 14, `build-logs` from row 18, `moderation` from row 19,
# `vehicles` from row 20, `admin` from row 21, `build-lists` from row 26 and
# `identity` from row 27 are cut today. The other two are filled in by rows 29
# and 31 and are listed empty so the script fails loudly with "no prefixes"
# rather than passing silently on an empty loop.
case "$DOMAIN" in
media)
  PREFIXES=(/api/images)
  ;;
build-logs)
  # Row 18.
  PREFIXES=(/api/build-logs)
  ;;
moderation)
  # Row 19. Three prefixes: votes and reports are polymorphic over an entity
  # type and bug reports share the domain, so this cut moves three route trees.
  PREFIXES=(/api/votes /api/reports /api/bug-reports)
  ;;
vehicles)
  # Row 20. Two prefixes: the car-generations read tree and the unified search,
  # which lives in this domain as seam 5's read fan-out.
  PREFIXES=(/api/car-generations /api/search)
  ;;
admin)
  # Row 21. Four prefixes, the most of any cut. Two are ordinary route trees and
  # two are the explicit children of /api/admin: there is no route at /api/admin
  # itself, and section 1.4 says no other domain may claim a child of it without
  # accounting for this, so the two are named rather than collapsed into one
  # broad prefix.
  PREFIXES=(/api/crawled-pages /api/part-price-alerts /api/admin/db-ops /api/admin/stats)
  ;;
build-lists)
  # Row 26. Four prefixes and the largest cut by route count, 34 of them. The
  # four are sibling trees rather than one tree with children: /api/build-lists
  # is the parent in the domain model but not in the URL space. A route key
  # matches literally rather than by string prefix, so /api/build-lists does not
  # claim /api/build-list-parts and neither claims row 18's /api/build-logs.
  PREFIXES=(/api/build-lists /api/build-list-parts /api/build-list-phases /api/build-list-labor-estimates)
  ;;
identity)
  # Row 27. One prefix and the fewest of any cut, with 24 routes under it: the
  # login and token routes, email verification, password reset, TOTP 2FA,
  # WebAuthn passkeys and Google OAuth. The three sub-prefixes /auth/2fa,
  # /auth/webauthn and /auth/oauth are paths below this one rather than siblings
  # of it, so one prefix covers the whole domain.
  #
  # Note for the no-credential fallback path below: there is no route at the
  # bare /api/auth, so a GET there answers 404 from a perfectly healthy
  # function, the same caveat row 26 recorded for three of its four prefixes.
  # The gateway path, which CI always takes, reads routeKey out of the access
  # log and has no such problem.
  PREFIXES=(/api/auth)
  ;;
catalog)
  # Row 29. Four prefixes and the largest cut of the nine by route count, 43 of
  # them: parts, part manufacturers, categories and retailers. The four are
  # sibling trees rather than one tree with children, and API Gateway matches a
  # route key literally, so /api/parts does not claim /api/part-manufacturers
  # and neither claims row 21's /api/part-price-alerts, which stays on admin.
  #
  # Every one of the four bare keys carries real traffic rather than sitting
  # there defensively, which is the first time that is true of a whole cut.
  # Seven routes mount with a trailing slash (a POST "/" and a GET "/" on parts,
  # part-manufacturers and retailers, and a GET "/" on categories) and the
  # gateway normalises those onto the bare key. So the no-credential fallback
  # caveat rows 26 and 27 recorded does not apply here: a GET on any of the four
  # bare paths reaches a real route on a healthy function.
  PREFIXES=(/api/parts /api/part-manufacturers /api/categories /api/retailers)
  ;;
users)
  # Row 31, the last cut. Two prefixes and 14 routes: the user accounts tree and
  # the global app-settings singleton. They are two sibling trees rather than one
  # tree with children, and a route key matches literally rather than by string
  # prefix, so /api/users claims neither row 27's /api/auth nor anything else.
  #
  # This is the one cut where the no-credential fallback path below is fully
  # sound on every prefix, which is the caveat rows 26, 27 and 29 each had to
  # qualify. Both bare keys carry real traffic (a GET "/" and a POST "/" in
  # users.py, a GET "/" and a PUT "/" in app_settings.py, all four mounting with
  # the trailing slash the gateway normalises onto the bare key), and both GETs
  # answer without a token: GET /api/users/ takes get_optional_current_user and
  # returns the public projection to an anonymous caller, and GET
  # /api/app-settings/ is public by design so the frontend can honour the
  # premium kill switch before anyone signs in. So a direct-invoke GET on either
  # bare path is a 200 from a healthy function rather than a 401 or a 404.
  #
  # /api/users/admin/users is section 1.4's ordering hazard for this domain and
  # nothing here touches it: the {proxy+} key hands the whole subtree to one
  # function, so FastAPI resolves it exactly as the whole-surface app did. Worth
  # knowing while reading a failure here: GET /{user_id} is registered before
  # GET /admin/users and the literal wins only on segment count, so a probe of
  # the bare /api/users/admin legitimately matches {user_id} and 404s.
  PREFIXES=(/api/users /api/app-settings)
  ;;
*)
  echo "Unknown domain: $DOMAIN" >&2
  usage
  ;;
esac

if [ ${#PREFIXES[@]} -eq 0 ]; then
  echo "No path prefixes are defined for domain '$DOMAIN' yet." >&2
  echo "That cut has not landed; add its prefixes here when it does." >&2
  exit 2
fi

PREFIX_NAME=carmodpicker-${ENV_NAME}
ACCESS_LOG_GROUP=/aws/apigateway/${PREFIX_NAME}-api
FUNCTION_NAME=${PREFIX_NAME}-${DOMAIN}

if [ -n "${CARMODPICKER_API_BASE_URL:-}" ]; then
  BASE_URL=${CARMODPICKER_API_BASE_URL%/}
elif [ "$ENV_NAME" = "production" ]; then
  BASE_URL=https://api.carmodpicker.com
else
  BASE_URL=https://api.staging.carmodpicker.com
fi

TIMEOUT=${CARMODPICKER_CURL_TIMEOUT:-20}
RETRIES=${CARMODPICKER_RETRIES:-5}
LOG_WAIT=${CARMODPICKER_LOG_WAIT:-120}
AWS_REGION_ARG=${AWS_REGION:-us-west-2}

FAILURES=0
NOT_CUT=0

# ---------------------------------------------------------------------------
# Fallback: no gateway, invoke the function directly.
#
# Proves the function serves the domain's paths. It cannot prove the gateway
# routes to it, which is the thing a cut actually changes, so this exits non
# zero on a broken function and prints a warning on a working one rather than
# reporting the cut verified.
# ---------------------------------------------------------------------------
invoke_fallback() {
  echo "Direct invoke fallback: probing ${FUNCTION_NAME} without the gateway."
  echo

  local event response status failed=0
  event=$(mktemp)
  response=$(mktemp)
  trap 'rm -f "$event" "$response"' RETURN

  for prefix in "${PREFIXES[@]}"; do
    # The bare prefix. The Web Adapter turns rawPath and the method into an
    # ordinary request against the application, so a 200, a 401 or a 422 all
    # prove the route is served; only a 404 says this application does not have
    # it. Most routes in a cut domain require a token, so 401 is the expected
    # healthy answer and is treated as such.
    #
    # A prefix with no route at the bare path answers 404 here and is reported
    # as a failure, which is a false negative rather than a real one. It applies
    # to /api/build-logs, /api/reports, /api/votes, /api/admin/db-ops,
    # /api/admin/stats and row 26's /api/build-list-parts,
    # /api/build-list-phases and /api/build-list-labor-estimates among others:
    # every route of those trees is below the
    # prefix, so a GET on the prefix itself is genuinely a 404 from a working
    # function. The gateway path above has no such problem, because it accepts
    # any answer that is not a 5xx and reads the route key out of the access
    # log, and CI always takes it: verify-route-cuts supplies
    # CARMODPICKER_ORIGIN_VERIFY on staging and needs no gate credential on
    # production. This fallback is the no-credential manual path, so read a 404
    # on a bare prefix here against the module's own routes before believing it.
    cat >"$event" <<JSON
{
  "version": "2.0",
  "routeKey": "ANY ${prefix}",
  "rawPath": "${prefix}",
  "rawQueryString": "",
  "headers": {
    "accept": "application/json",
    "host": "verify.invoke.local",
    "user-agent": "carmodpicker-verify-route-cut"
  },
  "requestContext": {
    "accountId": "anonymous",
    "apiId": "verify",
    "domainName": "verify.invoke.local",
    "http": {
      "method": "GET",
      "path": "${prefix}",
      "protocol": "HTTP/1.1",
      "sourceIp": "127.0.0.1",
      "userAgent": "carmodpicker-verify-route-cut"
    },
    "requestId": "verify",
    "routeKey": "ANY ${prefix}",
    "stage": "\$default",
    "time": "01/Jan/2026:00:00:00 +0000",
    "timeEpoch": 1767225600000
  },
  "isBase64Encoded": false
}
JSON

    aws lambda invoke \
      --function-name "$FUNCTION_NAME" \
      --region "$AWS_REGION_ARG" \
      --cli-binary-format raw-in-base64-out \
      --payload "file://$event" \
      --cli-read-timeout 60 \
      "$response" >/dev/null

    status=$(python3 -c '
import json, sys
try:
    payload = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    print("unparseable")
    sys.exit(0)
print(payload.get("statusCode", "missing") if isinstance(payload, dict) else "not-an-object")
' "$response")

    case "$status" in
    404 | missing | unparseable | not-an-object)
      echo "  ${prefix} -> ${FUNCTION_NAME} answered ${status}  FAIL"
      echo "        The function does not serve this path. The routes map"
      echo "        cannot fix that; the image or the entrypoint is wrong."
      failed=1
      ;;
    *)
      echo "  ${prefix} -> ${FUNCTION_NAME} answered ${status}  OK"
      ;;
    esac
  done

  echo
  if [ "$failed" -ne 0 ]; then
    echo "FAILED: ${FUNCTION_NAME} does not serve every '${DOMAIN}' prefix."
    return 1
  fi
  echo "WARNING: this ran without the gateway, so it did NOT verify the cut."
  echo "It proves ${FUNCTION_NAME} serves the '${DOMAIN}' prefixes and nothing"
  echo "more. Supply CARMODPICKER_ORIGIN_VERIFY or CARMODPICKER_GATE_COOKIE and"
  echo "run again to verify the routing."
  return 0
}

if [ "${CARMODPICKER_INVOKE_FALLBACK:-}" = "1" ]; then
  invoke_fallback
  exit $?
fi

# Gate credentials. The header is preferred because it is what a pipeline can
# use and it needs no browser.
GATE_ARGS=()
if [ -n "${CARMODPICKER_ORIGIN_VERIFY:-}" ]; then
  GATE_ARGS=(-H "x-origin-verify: ${CARMODPICKER_ORIGIN_VERIFY}")
  echo "Using the origin-verify header for the access gate."
elif [ -n "${CARMODPICKER_GATE_COOKIE:-}" ]; then
  GATE_ARGS=(-H "cookie: ${CARMODPICKER_GATE_COOKIE}")
  echo "Using the supplied gate cookie."
elif [ "$ENV_NAME" = "staging" ]; then
  echo "No CARMODPICKER_ORIGIN_VERIFY and no CARMODPICKER_GATE_COOKIE." >&2
  echo "Staging is behind the access gate, so every request below would be" >&2
  echo "answered by the gate with a 401 rather than by the API, and would" >&2
  echo "report as a failed cut that is really a missing credential." >&2
  echo "Falling back to a direct invoke of ${FUNCTION_NAME}." >&2
  echo >&2
  invoke_fallback
  exit $?
fi

echo "Verifying the '$DOMAIN' cut against $BASE_URL"
echo

# A marker unique to this run, sent in the user agent and matched in the access
# log. Matching on the marker rather than on the path is what makes the log read
# unambiguous when several runs, or real traffic, hit the same prefix.
MARKER="verify-${DOMAIN}-$(date +%s)-$$"

# One probe per prefix. Both route keys of a pair are exercised: the bare prefix
# and one path below it, because they are separate keys and a cut that creates
# only one of them half works, which section 3.5 calls the worst failure mode.
declare -a PROBE_PATHS=()
for prefix in "${PREFIXES[@]}"; do
  PROBE_PATHS+=("$prefix")
  PROBE_PATHS+=("${prefix}/verify-route-cut-probe")
done

# The route key each probe path should resolve to.
expected_key() {
  local path=$1 prefix
  for prefix in "${PREFIXES[@]}"; do
    if [ "$path" = "$prefix" ]; then
      echo "ANY ${prefix}"
      return
    fi
    case "$path" in
    "$prefix"/*)
      echo "ANY ${prefix}/{proxy+}"
      return
      ;;
    esac
  done
  echo ""
}

START_EPOCH_MS=$(($(date +%s) * 1000 - 60000))

for path in "${PROBE_PATHS[@]}"; do
  url="${BASE_URL}${path}"
  code=000
  for attempt in $(seq 1 "$RETRIES"); do
    code=$(curl -sS --max-time "$TIMEOUT" -o /dev/null -w '%{http_code}' \
      -A "$MARKER" "${GATE_ARGS[@]}" "$url" 2>/dev/null || echo 000)
    # 401 and 403 from the application are ordinary: most routes in a cut
    # domain require a token, and this probe carries none. What matters is that the
    # request reached the API at all, which any answer other than a gateway
    # level failure demonstrates. A 5xx can be a cold start, so it is retried.
    case "$code" in
    5* | 000)
      [ "$attempt" -lt "$RETRIES" ] && sleep 5
      ;;
    *)
      break
      ;;
    esac
  done

  case "$code" in
  5* | 000)
    echo "  ${path} -> HTTP ${code}  FAIL"
    echo "        The API did not answer. A cut cannot be verified against a"
    echo "        gateway that is erroring; fix that first."
    FAILURES=$((FAILURES + 1))
    ;;
  *)
    echo "  ${path} -> HTTP ${code}, reached the API"
    ;;
  esac
done

echo
echo "Waiting up to ${LOG_WAIT}s for ${ACCESS_LOG_GROUP} to catch up."

# The access log's format is the http-api module's default, which carries
# `userAgent`, `path` and `routeKey`. The marker rides in the user agent of every
# probe, so one filter pattern selects this run's entries and no other traffic's,
# and `path` and `routeKey` are then the pair the check needs.
#
# Delivery is per log stream and is not instant, and two requests a second apart
# can land in different streams that flush at different times. So this polls
# until every expected path has appeared rather than until some count is
# reached, and it accumulates across polls rather than trusting the last
# response: an entry seen at 20s is not lost because the query at 40s had not
# yet caught the other one.
#
# That accumulation is the fix for the first real CI failure of this script. The
# old loop broke when `len(events) >= len(PROBE_PATHS)` and otherwise polled to
# the deadline, then read only the final response. The bare path was delivered
# quickly and the `{proxy+}` path was not, so the count never reached two, the
# loop ran out the budget, and the last query happened to return only the one
# entry. It reported "no access log entry" for a path whose request had in fact
# been logged correctly, which reads as a routing failure and was not one.
FOUND_PATHS=$(mktemp)
trap 'rm -f "$FOUND_PATHS"' EXIT

DEADLINE=$(($(date +%s) + LOG_WAIT))
LOG_READ_OK=0
while :; do
  LOG_JSON=$(aws logs filter-log-events \
    --log-group-name "$ACCESS_LOG_GROUP" \
    --region "$AWS_REGION_ARG" \
    --start-time "$START_EPOCH_MS" \
    --filter-pattern "\"$MARKER\"" \
    --max-items 200 \
    --output json 2>/dev/null || echo '')

  if [ -n "$LOG_JSON" ]; then
    LOG_READ_OK=1
    # Append this poll's entries. Duplicates across polls are fine: the reader
    # below keeps the last value per path, and every poll reports the same
    # routeKey for a given path.
    printf '%s' "$LOG_JSON" | python3 -c '
import json, sys

try:
    events = json.load(sys.stdin).get("events", [])
except ValueError:
    sys.exit(0)
for event in events:
    try:
        entry = json.loads(event.get("message", ""))
    except ValueError:
        continue
    path = entry.get("path")
    key = entry.get("routeKey")
    if path is not None:
        print("%s\t%s" % (path, key))
' >>"$FOUND_PATHS" || {
      # Not silenced. A parser that cannot run is indistinguishable from a log
      # that has nothing in it once its output is discarded, and the failure this
      # script exists to report would then be reported for the wrong reason.
      echo "Failed to parse the access log response." >&2
      exit 1
    }
  fi

  # Done as soon as every probe path has an entry, however many polls that took.
  MISSING=0
  for path in "${PROBE_PATHS[@]}"; do
    if ! awk -F'\t' -v p="$path" '$1 == p { found = 1 } END { exit !found }' "$FOUND_PATHS"; then
      MISSING=$((MISSING + 1))
    fi
  done
  [ "$MISSING" -eq 0 ] && break

  NOW=$(date +%s)
  [ "$NOW" -ge "$DEADLINE" ] && break
  # Do not overshoot the deadline on the last sleep.
  REMAINING=$((DEADLINE - NOW))
  sleep "$([ "$REMAINING" -lt 5 ] && echo "$REMAINING" || echo 5)"
done

echo

if [ "$LOG_READ_OK" -eq 0 ]; then
  echo "Could not read ${ACCESS_LOG_GROUP}."
  echo "  Either the credentials cannot read it, or the access log is not"
  echo "  being written. The routeKey check is the whole verification, so this"
  echo "  is a failure rather than a skip."
  exit 1
fi

# One line per probe path is expected. If the gateway logged fewer, the probe
# that is missing gets reported by its absence rather than passing quietly.
ROUTE_KEYS=$(sort -u "$FOUND_PATHS")

for path in "${PROBE_PATHS[@]}"; do
  want=$(expected_key "$path")
  got=$(printf '%s\n' "$ROUTE_KEYS" | awk -F'\t' -v p="$path" '$1 == p { print $2 }' | tail -n1)

  if [ -z "$got" ]; then
    echo "  ${path} -> no access log entry after ${LOG_WAIT}s  FAIL"
    echo "        The request was not logged within the budget, so nothing can"
    echo "        be concluded about which integration served it. This is not"
    echo "        itself evidence of a bad route: the HTTP probe above reached"
    echo "        the API, and access log delivery is per stream and can lag."
    echo "        Raise CARMODPICKER_LOG_WAIT and run again before treating it"
    echo "        as a routing problem."
    FAILURES=$((FAILURES + 1))
    continue
  fi

  case "$got" in
  "$want")
    echo "  ${path} -> routeKey '${got}'  OK"
    ;;
  '$default')
    echo "  ${path} -> routeKey '\$default'  NOT CUT OVER"
    echo "        Matched the \$default route rather than '${want}'. That route"
    echo "        key did not land. Row 32 removed \$default entirely, so seeing"
    echo "        it here means this stage predates row 32."
    NOT_CUT=$((NOT_CUT + 1))
    ;;
  *)
    echo "  ${path} -> routeKey '${got}'  FAIL"
    echo "        Expected '${want}'. Another route key claims this path."
    FAILURES=$((FAILURES + 1))
    ;;
  esac
done

echo

# The authorizer check from section 6. It is deliberately separate from the loop
# above: a route created with authorization_type = NONE is a hole straight past
# the gate, and it is invisible to a check that always sends the credential.
if [ "$ENV_NAME" = "staging" ] && [ ${#GATE_ARGS[@]} -gt 0 ]; then
  probe=${PROBE_PATHS[0]}
  bare=$(curl -sS --max-time "$TIMEOUT" -o /dev/null -w '%{http_code}' \
    "${BASE_URL}${probe}" 2>/dev/null || echo 000)
  case "$bare" in
  401 | 403)
    echo "Gate check: ${probe} without a credential returned HTTP ${bare}  OK"
    ;;
  *)
    echo "Gate check: ${probe} without a credential returned HTTP ${bare}  FAIL"
    echo "  That route is past the access gate. Check that its routes entry"
    echo "  sets no authorization_type, so the module applies CUSTOM."
    FAILURES=$((FAILURES + 1))
    ;;
  esac
fi

echo
if [ "$FAILURES" -gt 0 ]; then
  echo "FAILED: ${FAILURES} check(s) did not verify."
  exit 1
fi
if [ "$NOT_CUT" -gt 0 ]; then
  echo "NOT CUT OVER: ${NOT_CUT} path(s) resolved to \$default rather than to"
  echo "their own route key. The Terraform apply has not landed, or the routes"
  echo "map does not name these prefixes. Since row 32 there is no \$default"
  echo "route, so a prefix whose key did not land 404s at the gateway instead of"
  echo "reaching this branch."
  exit 1
fi

echo "Every '${DOMAIN}' path resolves to its own route key, not \$default."
