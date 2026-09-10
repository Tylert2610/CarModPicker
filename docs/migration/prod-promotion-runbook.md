# Production promotion runbook: domain split rows 14 to 22

The executable sequence for promoting `staging` to `main` and standing the domain
split up in the production account for the first time. Section 6.6 of
`split-plan.md` is the design; this is the operator's copy, with the exact
command for each step, what a good result looks like, and the condition that
stops the release.

Production account `734702670403`, region `us-west-2`, HCP workspace
`ws-oh1VvpTBPxmcrSYD` (`CarModPicker`, Terraform 1.14.8, VCS branch `main`, no
auto-apply). Read-only profile `CarModPicker-Production/ReadOnlyAccess`.

Production is a fresh account for everything this release adds. Verified before
the release: no ECR repositories, one Lambda (`carmodpicker-production-api`),
X-Ray trace segment destination `XRay` rather than `CloudWatchLogs`, and a deploy
role carrying no CodeArtifact or ECR grants. That is why the bootstrap path in
6.6 applies here rather than the ordinary promote-and-apply.

**Correction, row 32.** This runbook was written while the monolith
(`carmodpicker-production-api`) was still the function on `$default`, and most of
its counts, health checks and rollback levers assumed a monolith would be there
to fall back to. Row 32 of `split-plan.md` retired it: the function, the zip
chain, the artifacts bucket and the `$default` route are all gone, and
`default_integration` is `null`. The steps below are annotated where that changes
what to expect or what to do. The sequence itself still holds, because the
sequencing hazards it was written around, functions and routes landing in the
same apply and the bootstrap tag expiring, are unchanged. Section 9 changed the
most and should be read in full before anyone rolls anything back.

---

## 0. Preconditions

Confirm all of these before merging. Each is a hard gate.

| Check | Command | Expected |
| --- | --- | --- |
| Both bootstrap variables exist on the prod workspace | `curl -sg -H "Authorization: Bearer $TOK" https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars` | `bootstrap_image_tag` = `""` and `adopt_spans_log_group` = `"false"`, both `terraform` category, neither sensitive, neither HCL |
| The prod speculative plan is green and has been read | Release PR checks, `Terraform Cloud/WebbPulse` | `planned_and_finished`, and the categorised diff reviewed against section 4 below |
| No apply is in flight on the prod workspace | `GET /api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/runs?page[size]=3` | Newest run is `applied` or `planned_and_finished` |
| The API is healthy | See the note below | `200` from a real domain prefix |

**Abort if** either variable is missing or holds a different value. Applying with
`adopt_spans_log_group` at its default of `true` is a plan time error in this
account, because the `aws/spans` log group does not exist yet and an import block
whose target is absent fails the plan rather than skipping.

**The health check changed in row 32.** `curl -si https://carmodpicker.com/api/health`
was the liveness probe here because `/health` fell through to the monolith on
`$default`. With no `$default` route, `/health` matches no route key and the
gateway answers `404` whether or not anything behind it is healthy, so that curl
now proves nothing. Two replacements, and they answer different questions:

- **Gateway liveness.** Probe a real domain prefix, for example
  `curl -si https://carmodpicker.com/api/app-settings/`, which is public by design
  and expects `200`. Any prefix in `local.lambda_domain_path_prefixes` works; pick
  one that needs no credential so a non-`200` is unambiguous.
- **Per-function liveness.** `aws lambda invoke` with a synthesised HTTP event
  against the function directly, which is exactly what `deploy-backend.yml`'s
  `smoke-domains` job does. That is the only way to reach `/health` on a domain
  function now, because each entrypoint still serves the five root routes even
  though the gateway routes none of them.

---

## 1. Merge the release PR

```
gh pr merge <release-pr> --repo WebbPulse/CarModPicker --merge
```

The merge to `main` starts a VCS-driven run on `ws-oh1VvpTBPxmcrSYD`. It does not
auto-apply. It also starts `Frontend Deploy` and `Backend Deploy` on `main`, and
the Chrome extension's live Web Store publish, which runs only when the merge
carries a `chrome-extension/**` change.

The extension publish derives its version from the newest `chrome-extension-v*`
tag rather than from a commit on `main`. It patches `manifest.json` in the build
output only, publishes to the Web Store, then pushes the annotated tag
`chrome-extension-v<version>`. It never pushes a commit to `main`, so the
`main-protection` ruleset does not block it. Afterwards it opens a bookkeeping PR
against `staging` that realigns the committed manifest with the published
version. That PR is bookkeeping only: the release is already live and tagged by
the time it is opened, so it can be merged whenever convenient, and closing it
does not affect the next release. If the org does not allow Actions to open pull
requests, the job pushes the branch anyway and prints a compare URL in the job
summary.

**Expected:** a run appears on the prod workspace and reaches `planned`, waiting
for confirmation. `Frontend Deploy` and `Backend Deploy` **fail** at the
CodeArtifact login step. That failure is expected and is not a reason to stop:
the production deploy role carries only S3, Lambda and CloudFront actions today,
and the CodeArtifact, ECR, SSM and `sts:GetServiceBearerToken` grants arrive with
apply 1. Nothing is broken by the failure, because neither workflow had reached a
step that changes production.

**Abort if** the run errors at plan time. Read the error verbatim before doing
anything else; a plan time error here is almost always the `aws/spans` import or a
provider upgrade surprise, and neither is fixed by retrying.

---

## 2. Apply 1: everything except the domain functions and routes

Confirm the run created by the merge, with `bootstrap_image_tag` still `""`.

```
curl -sg -X POST -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/vnd.api+json" \
  -d '{"comment":"Apply 1: bootstrap, no domain functions or routes"}' \
  https://app.terraform.io/api/v2/runs/<run-id>/actions/apply
```

**Creates:** the nine ECR repositories, every IAM role including the CodeArtifact
statements the deploy and CI roles need, the DynamoDB stream enablement on
`users`, `parts`, `votes` and `part_listings`, the four stream dead letter queues,
the `part-purge` and `user-delete` work queues with their DLQs, the Transaction
Search resource policy, destination and indexing rule, and the alarm set at module
`~> 2.4`. It creates **no domain function and cuts no route**, because
`local.lambda_domains` and `local.routed_lambda_domains` both resolve to empty
while `bootstrap_image_tag` is `""`.

**Also destroys:** `carmodpicker-production-lambda-errors` and
`carmodpicker-production-lambda-throttles`, replaced by the aggregate pair from
the newer alarm module. Accepted by the owner.

**Verify:**

```
export AWS_REGION=us-west-2 AWS_PROFILE=CarModPicker-Production/ReadOnlyAccess
aws ecr describe-repositories --query 'repositories[].repositoryName' --output text
aws iam get-role-policy --role-name carmodpicker-production-github-actions-deploy \
  --policy-name deploy-permissions --query 'PolicyDocument.Statement[].Action' --output json \
  | grep -c codeartifact
aws lambda list-functions --query 'Functions[].FunctionName' --output text
aws dynamodb describe-table --table-name carmodpicker-production-users \
  --query 'Table.StreamSpecification'
aws xray get-trace-segment-destination
```

Expected: nine repositories, all empty; a non-zero CodeArtifact action count on the
deploy role; still exactly one Lambda (`carmodpicker-production-api`);
`StreamEnabled: true` with `StreamViewType: NEW_AND_OLD_IMAGES`; trace segment
destination `CloudWatchLogs` with status `ACTIVE`.

**Abort if** the apply fails partway. A partial apply here leaves the account in a
mixed state but breaks nothing serving traffic: no route has moved. (When this
was written the reassurance was that the monolith was still on `$default`. After
row 32 the reassurance is narrower and still true: this apply creates
repositories, grants and streams and touches no route, so a partial failure here
cannot move traffic off a function that is already serving it.) Fix forward rather than reverting, because the
stream enablement in this apply is not reversible by a revert (see section 7).

---

## 3. Push the images

Dispatch `Deploy Backend` on `main` with `BACKEND_IMAGE_BUILD_ENABLED` set as a
repository variable and `BACKEND_IMAGE_DEPLOY_ENABLED` still unset.

```
gh workflow run deploy-backend.yml --repo WebbPulse/CarModPicker --ref main
gh run watch <run-id> --repo WebbPulse/CarModPicker
```

**Expected:** green. The build pushes nine images tagged `sha-<commit sha>`. The
`existing-functions` job finds no domain functions, drops all nine from the image
map, and `deploy-images`, `smoke-domains` and `verify-route-cuts` skip on the
empty map. A green run with three skipped jobs is the correct outcome, not a
half-run.

**Record the exact sha the build ran on**, not what `main` points at afterwards:

```
gh run view <run-id> --repo WebbPulse/CarModPicker --json headSha -q .headSha
```

**Verify** the tag landed in every one of the nine repositories:

```
SHA=<the sha above>
for d in media build-logs moderation vehicles admin build-lists identity catalog users; do
  printf '%-12s ' "$d"
  aws ecr describe-images --repository-name carmodpicker-production/$d \
    --image-ids imageTag=sha-$SHA --query 'imageDetails[0].imagePushedAt' --output text 2>&1
done
```

**Abort if** any of the nine returns `ImageNotFoundException`. Apply 2 creates
five functions from this one tag and `CreateFunction` resolves it for real; a tag
missing from even one declared domain's repository fails the apply partway
through, and the speculative plan cannot detect it because the plan renders the
image URI as an unresolved string.

---

## 4. Set the seed tag

```
curl -sg -X PATCH -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/vnd.api+json" \
  -d '{"data":{"type":"vars","id":"var-AHD2StDs2s8rtcVG","attributes":{"value":"sha-'"$SHA"'"}}}' \
  https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars/var-AHD2StDs2s8rtcVG
```

**Expected:** `200`, with `value` echoed as `sha-<40 hex>`. The variable validation
rejects anything that is not `sha-` plus forty hex characters or the empty string,
so a malformed value fails at plan time rather than at apply time.

---

## 5. Apply 2: functions and routes together

Start a run on the prod workspace and confirm it.

```
curl -sg -X POST -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/vnd.api+json" \
  -d '{"data":{"attributes":{"message":"Apply 2: domain functions and route cuts"},"type":"runs","relationships":{"workspace":{"data":{"type":"workspaces","id":"ws-oh1VvpTBPxmcrSYD"}}}}}' \
  https://app.terraform.io/api/v2/runs
```

Read the plan before confirming. **Expected:** five domain functions (`media`,
`build-logs`, `moderation`, `vehicles`, `admin`, the entries in
`local.lambda_domains_declared`), each with its role, log group, two policies and
runtime policy; the API Gateway integration, permission and two route keys per
prefix for every routed domain; two metric filters per function; and the aggregate
Lambda alarm pair, which apply 1 could not create because there was nothing to
sum.

Functions and routes must land in the **same** apply. `verify-route-cuts`
hardcodes its domain list, so a function that exists without its routes makes that
job probe the prefix, read `routeKey: $default`, and exit 1.

**Verify:**

```
aws lambda list-functions --query 'Functions[].FunctionName' --output text
aws apigatewayv2 get-apis --query 'Items[].ApiId' --output text
```

Expected: six functions (the monolith plus five domains), and the route table
carrying the per-domain route keys alongside `$default`.

**After row 32** the monolith is not in the count and there is no `$default` row
in the route table. On an estate at row 32 the same check reads: thirteen
functions, the nine domains plus the four stream consumers, and a route table of
per-domain route keys only. Adjust the number to the rows the apply you are
running actually creates rather than reading `six` literally.

**Abort if** the apply fails on `CreateFunction` with an image resolution error.
That means the seed tag was expired out of a repository between step 3 and here by
the keep-last-10 lifecycle. The fix is to re-dispatch the build, refresh the
variable to the new sha, and re-run this apply, not to retry the same run.

---

## 6. Deploy the images and verify the cuts

Set `BACKEND_IMAGE_DEPLOY_ENABLED` and dispatch `Deploy Backend` on `main` again.

```
gh workflow run deploy-backend.yml --repo WebbPulse/CarModPicker --ref main
```

**Expected:** `existing-functions` now finds the five functions, `deploy-images`
points each at its digest, `smoke-domains` probes them, and `verify-route-cuts`
passes. **`verify-route-cuts` passing is the gate that says the release worked.**

**Abort if** `verify-route-cuts` fails. Read which prefix it reports. A prefix
reading `$default` means the route for a created function did not land, which is
the failure mode step 5 is sequenced to prevent. Treat it as a live traffic issue.
Before row 32 that meant the monolith was serving the prefix while the domain
function believed it owned it, which was wrong but not an outage. After row 32
there is no `$default` route to report, so the same failure surfaces as a `404`
from the gateway and the prefix is genuinely down. The urgency went up, not down.

---

## 7. Post-release verification

Run this list once step 6 is green.

- **Prod smoke.** Probe a public domain prefix rather than `/api/health`; after
  row 32 `/health` is not routed and returns `404` from the gateway regardless of
  health. `curl -si https://carmodpicker.com/api/app-settings/` returning `200` is
  the equivalent check.
  Exercise one route per cut domain through the site, not only the API, so the
  CloudFront and CORS paths are covered too. The CORS and verify-email host fixes
  in this release change response headers, so a browser check is worth more than
  a curl here.
- **`verify-route-cuts` on `main`.** Green, from step 6.
- **Chrome Web Store publish.** `gh run list --workflow chrome-extension-deploy.yml
  --repo WebbPulse/CarModPicker --branch main --limit 1`. This job publishes live.
  If it failed, the extension in the store is the previous version and the site is
  unaffected; if it succeeded, the new version is rolling out to users. Confirm the
  published version by checking that the tag `chrome-extension-v<version>` exists,
  because the tag is pushed only after the Web Store publish succeeds. The
  committed `chrome-extension/manifest.json` trails the tag until the bookkeeping
  PR against `staging` merges, so it is not the version of record.

  **This release:** the publish for v1.1.18 did not happen. The run for merge
  `46a28433` failed at the old "Commit version bump and push tag" step, because
  that step pushed a commit straight to `main` and the `main-protection` ruleset
  rejected it with `GH013`. No tag was pushed and nothing reached the Web Store,
  so `main` is still at manifest 1.1.17. Once the workflow fix has merged to
  `staging` and been promoted to `main`, re-run the publish by hand:

  ```
  gh workflow run chrome-extension-deploy.yml --repo WebbPulse/CarModPicker --ref main
  ```

  `workflow_dispatch` needs no `chrome-extension/**` diff, so this republishes the
  release without another merge. The run derives v1.1.18 from the newest tag
  `chrome-extension-v1.1.17` on its own.
- **Alarms.** `aws cloudwatch describe-alarms --query 'MetricAlarms[].[AlarmName,StateValue]'
  --output text`. Expected: `carmodpicker-production-lambda-errors` and
  `carmodpicker-production-lambda-throttles` are gone, replaced by the aggregate
  pair; `api-5xx`, `api-integration-latency-p99`, `application-errors` and
  `dynamodb-throttles` are all `OK`. An `INSUFFICIENT_DATA` on a new aggregate
  alarm is normal for the first few minutes.
- **Alarm delivery still works.** `aws sns list-subscriptions-by-topic --topic-arn
  arn:aws:sns:us-west-2:734702670403:carmodpicker-production-alarms`. Two confirmed
  email subscriptions. The topic is not replaced by this release, so these should
  be untouched; check anyway, because an alarm nobody receives is worse than a
  missing alarm.
- **`aws/spans` appears.** `aws logs describe-log-groups --log-group-name-prefix
  aws/spans`. X-Ray creates it on the first span export after traffic reaches a
  domain function, at its own 30 day default. It will not exist immediately after
  step 6; give it a few minutes of real traffic.

## 8. Apply 3: adopt `aws/spans`

Only once the group exists. Set `adopt_spans_log_group` to `true`
(`var-NEt5fWC2nNbZGikc`) and start a run.

**Expected:** a plan of exactly one import and one retention change, 30 days to 7.
Anything else in that plan means something drifted between apply 2 and here and
should be read before confirming.

**Verify:** `aws logs describe-log-groups --log-group-name-prefix aws/spans
--query 'logGroups[0].retentionInDays'` returns `7`.

**Abort if** the plan errors on the import. That means the group still does not
exist and the variable was flipped too early. Set it back to `false`, discard the
run, and wait for traffic.

---

## 9. Rollback

Reverting `main` to the previous sha is **not** a full rollback. What it does and
does not undo is the part to be clear about before anyone reaches for it.

**Correction, row 32: there is no monolith to fall back to.** Everything below
was written while `carmodpicker-production-api` was on `$default` and would catch
any route the domain functions stopped serving. Row 32 deleted the function and
the `$default` route. Deleting a domain's route keys no longer sends its traffic
anywhere; it makes that prefix `404` at the gateway. Read the "after row 32"
paragraph under each bullet, not only the bullet.

**A revert plus an apply does undo:**

- The five domain functions and their roles, log groups and policies, because
  `bootstrap_image_tag` on the workspace would then name a tag no longer
  referenced by any declared domain. Clearing the variable back to `""` does the
  same thing more directly and is the honest lever.

  **After row 32 this is a destructive lever, not a safe one.** It destroys the
  functions that serve every API route, and nothing replaces them. Do not reach
  for it to fix a traffic problem.
- The API Gateway route cuts. Traffic returns to the monolith on `$default`, which
  is the meaningful half of the rollback: the monolith still serves every route it
  served before this release, so this restores working behaviour.

  **After row 32 this is false.** With `default_integration = null` there is no
  fallback integration, so removing a domain's route keys removes the only thing
  that serves that prefix and it starts answering `404`. Deleting route keys is
  correct only when you are also restoring something to serve them, which in
  practice means putting the monolith or an equivalent back on `$default` first.
  Nothing in the current configuration does that, and re-creating the monolith is
  not a fast operation: it is a revert of row 32's Terraform plus an image or zip
  to run. Treat route deletion as a planned change, never as an incident lever.
- The aggregate Lambda alarm pair, and it restores the monolith's two alarms at
  the older module version.

  **After row 32 there are no monolith alarms to restore.** The monolith was never
  in `lambda_function_names`, so it had no aggregate slot to give back and nothing
  renumbers. What row 32 actually removed on the monitoring side is two metric
  filters, `errors["api"]` and `rate_limit_failed_open["api"]`, and the two alarm
  descriptions that named 14 error log groups now name 13. The aggregate chunking
  is unchanged.

**A revert does not undo:**

- **DynamoDB streams.** Enabling a stream is an in-place `UpdateTable`, and the
  stream view type cannot be edited once the stream exists. A revert that disables
  the streams and a later re-enable mints a **new stream ARN**, silently detaching
  every consumer reading the old one. Rows 24 and 25 add those consumers, so today
  the practical advice is to leave the streams enabled through any rollback. They
  cost nothing while nothing reads them.
- **Transaction Search.** The trace segment destination is an account-wide setting.
  A revert flips it back toward `XRay`, but the `aws/spans` log group and every
  span already written to it remain. Setting `adopt_spans_log_group = false` drops
  the group from Terraform state without deleting it in AWS, which is a state
  change and not a data change.
- **The nine ECR repositories and the images in them.** They are harmless and
  re-creating them is the slow part of a re-promotion, so leaving them is
  preferable.
- **The tombstone attributes** `deleted` and `deleted_at` on `users` and `parts`.
  They are new attributes on existing items with no backfill, so a revert leaves
  them where they were written and the old code simply ignores them.
- **The Chrome Web Store publish.** Once a version is live it is live. Rolling the
  extension back means publishing another version, not reverting a commit.

**The fastest safe rollback**, if traffic is misbehaving after step 5 or 6, is to
set `bootstrap_image_tag = ""` on the workspace and apply. That destroys the domain
functions and the route cuts in one apply and puts every route back on the
monolith, without touching the streams, the repositories, the tables or
Transaction Search. Reverting the merge commit on `main` is the slower path and
buys nothing extra for the traffic problem.

**After row 32 that lever is gone and the rollback is the image, not the route.**
Clearing `bootstrap_image_tag` now destroys the functions and leaves nothing
behind them, which turns a degraded API into a fully dead one. The rollback for a
bad domain deploy is to put the previous image back on the function that has it:

```
aws lambda update-function-code \
  --function-name carmodpicker-production-<domain> \
  --image-uri <account>.dkr.ecr.us-west-2.amazonaws.com/carmodpicker-production/<domain>@sha256:<previous digest> \
  --region us-west-2
aws lambda wait function-updated-v2 --function-name carmodpicker-production-<domain>
```

Take the previous digest from the `deploy-images` job of the last good
`Deploy Backend` run, or from `aws ecr describe-images --repository-name
carmodpicker-production/<domain>` by `imagePushedAt`. This is per function, so it
rolls back exactly the domain that regressed and leaves the other eight on the
current image, which is a smaller blast radius than any Terraform lever ever was.
It also touches no route, no stream and no table.

Two caveats worth knowing before you need them. The ECR lifecycle policy keeps
only the last ten `sha-` tagged images per repository, so a digest more than ten
deploys old may no longer resolve; if it does not, the rollback is a rebuild of
that commit rather than a digest swap. And a bad *route* cut is still a Terraform
problem rather than an image problem: if a prefix is `404`ing because its route
keys are wrong, the fix is to correct and apply `local.lambda_domain_path_prefixes`,
because there is no longer a `$default` route papering over a mismatch while you
work it out.
