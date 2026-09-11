# Production promotion runbook

How the identity adoption and the rest of the domain split that live on
`staging` reach `main`, which is production.

This is the ordered checklist for one specific promotion: merging `staging` into
`main` and applying it to the production workspace `ws-oh1VvpTBPxmcrSYD`. It
assumes `docs/identity-adoption.md` has been read, because that document
explains what the rows are and why each script exists, and
`docs/identity-migration-runbook.md`, which owns the script order in detail.
This one is narrower: the order, the exact commands, the plan shapes to expect,
and the gates that stop the promotion.

It is modelled on the Portfolio runbook of the same name, and it is written
after that runbook was actually executed on 2026-09-11. Three things went wrong
there that no amount of reading the code would have predicted, and each one has
a step here that exists only because of it. They are called out where they
apply.

**Nothing in this document is authorised to run itself.** Every merge, every
apply and every write below is an owner decision.

## State at the time of writing, 2026-09-10

Verified against the live accounts and the live workspaces rather than assumed.

| Thing | Staging (748861776298) | Production (734702670403) |
| --- | --- | --- |
| Branch | `staging`, 29 commits ahead of `main` | `main` |
| HCP workspace | `ws-dNLoiEHVxr2o81XM` | `ws-oh1VvpTBPxmcrSYD` |
| Declared domains in `lambda_domains.tf` | nine | **five**: `media`, `build-logs`, `moderation`, `vehicles`, `admin` |
| `terraform/identity.tf` | present | **absent from `main` entirely** |
| `identity_jwt_mode` | `gate` | unset, so `off` by default |
| `domain_jwt_enforced` | unset, so `false` | unset, so `false` |
| Identity stack | applied | none: no KMS key, no identity tables |
| DynamoDB tables | identity set present | **26 tables, none of the ten identity names** |
| Customer-managed KMS keys | signing and MFA keys present | **zero**, only the 14 `alias/aws/*` managed aliases |
| Lambda functions | nine domains plus consumers | **seven**: the `api` monolith, five domains, one consumer |
| `carmodpicker-production-identity` | exists | **does not exist** |
| Gateway routes | the full set | **23, every one `AuthorizationType: NONE`** |
| Gateway authorizers | gate REQUEST authorizer | **none**, `get-authorizers` returns `[]` |
| `/api/auth` route keys | the generated pair plus row 8's fifteen | **none at all**, auth falls through `$default` to the monolith |
| Discovery document | `200` at the staging API host | **`404`** at `https://api.carmodpicker.com/api/auth/.well-known/openid-configuration` |
| Frontend `AUTH_MODE` | **unset**, so `bearer` | **unset**, so `bearer` |
| Extension `authMode` | runtime setting, default `legacy` | runtime setting, default `legacy` |
| SES sandbox | in sandbox | in sandbox, `ProductionAccessEnabled: false` |
| Legacy users | synthetic plus the owner's row | **174 real user rows** |

### The numbers that matter

- **`carmodpicker-production-users` holds 174 items.** Confirmed by a
  `--select COUNT` scan, single page, and `describe-table` agrees. Deletion
  protection is on. This is the table step 6 migrates, and it is the single
  biggest difference from Portfolio, whose production users table held exactly
  one row.
- **`carmodpicker-production-oauth_accounts` holds 93 items** and
  `carmodpicker-production-webauthn_credentials` holds 2, both under the legacy
  underscore schema. Neither is touched by this promotion. They are row 13's
  problem, not this one's.
- A large fraction of the 174 rows will be Google-only accounts with no
  `hashed_password`. `migrate_credentials_to_identity.py` counts those
  separately as `skip_oauth_only` precisely so that they do not read as data
  loss. Expect that number to be substantial and do not treat it as a fault.

### What `main` lacks against `staging`

The 29 commits carry rows 6 and 8 through 12 of the identity adoption, plus
rows 25 to 32 of the domain split. Concretely, promoting lands all of:

- Four more domain functions, `build-lists`, `catalog`, `identity` and `users`,
  and their route cuts. Production runs five of the nine today.
- The retirement of the monolith, `$default`, the legacy artifacts bucket and
  the zip chain, which is row 32.
- The whole identity stack: `terraform/identity.tf`, two KMS keys, the ten
  identity tables, three IAM role policies and the SES grant.
- Row 8's fifteen explicit `/api/auth` route keys, marked `require_identity_jwt`.
- Row 12a's eighty explicit domain route keys plus two anonymous guard keys,
  landing unmarked because `var.domain_jwt_enforced` defaults to `false`.
- The frontend `AuthClient` behind `VITE_AUTH_MODE` and the Chrome extension
  sign-in handoff.

## Blockers, to be settled before anything is merged

### 1. The production plan errors today, and it does not fix itself

> **FIXED, 2026-09-10.** Option C below was taken.
> [`terraform-aws-platform-modules` PR 46](https://github.com/WebbPulse/terraform-aws-platform-modules/pull/46)
> added an `attach_role_policies` input to `modules/identity` and moved all three
> counts onto it, released as **`v2.10.0`**. CarModPicker PR 415 bumped the pin in
> `terraform/identity.tf` from `~> 2.7` to `~> 2.10` and passes
> `attach_role_policies = true`.
>
> A speculative plan of that branch against the production workspace
> `ws-oh1VvpTBPxmcrSYD` (run `run-6gtpiUqZf6bxbfmF`) now reaches
> `planned_and_finished` and renders a diff: **201 to add, 6 to change, 18 to
> destroy**. The previous attempt reached `errored` with `Invalid count argument`
> and no diff at all, so the gate this section names is met.
>
> The three policies plan as `module.identity.aws_iam_role_policy.identity_signing[0]`,
> `identity_tables[0]` and `identity_mfa[0]`, plain creates at a known index,
> which is precisely what the unknown count made impossible.
>
> **Every hard stop in step 3 passes on that plan**, checked against the plan
> JSON rather than by eye: zero DynamoDB table destroys, zero
> `aws_apigatewayv2_authorizer` of any action, zero Route 53 record changes, and
> zero destroys anywhere under `module.identity`. The 18 destroys are row 32's
> monolith retirement and nothing else, itemised in step 3. The 6 changes are
> five alarm and policy updates that follow from adding domains, plus the
> `github_actions_role` policy.
>
> The staging workspace `ws-dNLoiEHVxr2o81XM` (run `run-xeNGeMRSE4xPkcji`) is
> zero-change against the same branch, which is the other half of the check: the
> fix is a plan-time change, and staging, whose identity role already exists and
> whose id was therefore always known, must not move at all.
>
> Both runs were speculative configuration versions, which HCP refuses to apply
> by construction, so neither could be confirmed against production.
>
> The rest of this section is kept as written because it explains why the fix
> takes the shape it does, and because the same trap applies to any future module
> input that counts off a consumer's computed value.

This was the one real blocker and it needed a code change before the merge.

A speculative plan of the `staging` tree against production state fails with
`Invalid count argument` in `module.identity`, in the module's `kms.tf` and
`dynamodb.tf`. The mechanism is exact and worth writing down, because the
obvious reading of it is wrong.

`terraform/identity.tf` wires the module to the identity function's role:

```hcl
identity_role_name = module.lambda_domain["identity"].role_id
identity_role_arn  = module.lambda_domain["identity"].role_arn
```

Inside the module, three resources count off that input:

```hcl
# modules/identity/kms.tf
resource "aws_iam_role_policy" "identity_signing" {
  count = var.identity_role_name == null ? 0 : 1
}
resource "aws_iam_role_policy" "identity_mfa" {
  count = var.identity_role_name == null || !local.mfa_key_exists ? 0 : 1
}
# modules/identity/dynamodb.tf
resource "aws_iam_role_policy" "identity_tables" {
  count = var.identity_role_name == null || length(var.tables) == 0 ? 0 : 1
}
```

`role_id` is `aws_iam_role.this.id`. In production that role does not exist:
`main` declares five domains and `identity` is not one of them, so
`module.lambda_domain["identity"]` is a resource the plan intends to create.
Its `id` is therefore unknown at plan time, the `count` expression is unknown,
and Terraform refuses to plan at all. That is what `Invalid count argument`
means: not that the value is wrong, but that Terraform cannot decide how many
instances of the resource to make before it has applied something else.

**A first apply with `identity_jwt_mode` absent does not resolve this.** That
is worth stating plainly because it is the intuitive guess and it is false.
`identity_jwt_mode` gates `local.identity_jwt_native_enforced`, which gates
`module.api`'s `identity_jwt` input and the `identity_jwt_depends_on` list. It
does not gate `module.identity` at all. The module is called unconditionally in
`identity.tf` and its three role policies count off the role name whatever the
mode is. Leaving the variable absent avoids the `CreateAuthorizer` failure and
nothing else; the plan still cannot be produced.

The module's own comment, at `kms.tf` line 228, describes this exact class of
failure for the neighbouring MFA policy and explains why that one was written
against the input variables rather than against a computed ARN. The three
policies above take the role name directly and so are still exposed to it.

There are three ways out and the owner picks one.

| Option | What it is | Cost |
| --- | --- | --- |
| **A. Two-phase by `bootstrap_image_tag`** | Set `bootstrap_image_tag = ""` on the production workspace, apply, then set the real sha and apply again | Resolves `local.lambda_domains` to `{}`, so `module.lambda_domain["identity"]` does not exist and the plan fails on a *missing map key* instead. Does not work. |
| **B. `-target` the identity function first** | Apply `module.lambda_domain["identity"]` alone, then apply the rest | Works, because the role is real by the second plan. Requires a targeted apply through the HCP API, which is a deliberate departure from how every other apply in this repository runs. |
| **C. Make the count plan-time known** ✅ **taken** | Change the module so the three policies count off a plan-time boolean rather than off the role name | The correct fix. It is a `platform-modules` change and a version bump, and it is what the module already does for `local.mfa_key_exists`. Shipped as `v2.10.0`. |

**Recommendation: C, as a `platform-modules` release, with B as the fallback if
the owner wants the promotion to go this week.** C is a small change: add a
`create_role_policies` input defaulting to `var.identity_role_name != null`
evaluated against the variable's own nullness is not enough, because the
variable is non-null but unknown. The shape that works is an explicit boolean
input the consumer sets, which is known at plan time by construction.

**What actually shipped**, and it is that shape. `v2.10.0` adds
`attach_role_policies`, a `bool` defaulting to `true`, and the three counts read
it:

```hcl
count = var.attach_role_policies ? 1 : 0                              # kms.tf, signing
count = var.attach_role_policies && local.mfa_key_exists ? 1 : 0      # kms.tf, mfa
count = var.attach_role_policies && length(var.tables) > 0 ? 1 : 0    # dynamodb.tf, tables
```

Both remaining operands were already plan-time known: `local.mfa_key_exists`
reads two input variables for this same reason, and `var.tables` is an input.

`identity_role_name = null` keeps its old meaning of attaching nothing, now
written as the pair `attach_role_policies = false`. The halfway state, true with
a null role name, is refused by a `validation` on `identity_role_name` whose
condition is `!var.attach_role_policies || var.identity_role_name != null`. That
reads only the two variables and nothing computed, so it stays decidable at plan
time even when the role name's value is not: a validation checks whether the
value is null, and an unknown non-null value is not null. That distinction is
the whole of why the fix works.

Either way, **do not merge until a production speculative plan renders.** A
plan that cannot be produced is not a plan with a surprising shape; it is a
merge that queues a run which errors before it shows a diff, on a branch that
auto-deploys. This gate is now satisfied; re-run it against the actual promotion
branch anyway, since it is cheap and the branch will have moved.

Confirm the fix the same way every other gate here is confirmed:

```bash
T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
curl -s -H "Authorization: Bearer $T" \
  "https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/runs?page%5Bsize%5D=1" \
  | jq -r '.data[0] | {id, status: .attributes.status}'
```

A speculative plan that reaches `planned_and_finished` and shows a diff is the
gate. Anything that reaches `errored` is not.

### 2. `staging` and `main` have diverged, but the merge is clean

Portfolio's promotion pull request opened conflicting, because a privacy page
landed directly on `main` while the same change was applied separately to
`staging`. Its runbook now says to check for this, so this one checks it and
records the answer rather than assuming.

`main` carries two non-merge commits that `staging` does not have:

```
adb1bd7d fix(chrome-extension): release by tag instead of pushing to main (#376)
1260925d chore(deps): bump actions/setup-python from 6 to 7 (#300)
```

So `git merge-base --is-ancestor origin/main origin/staging` is **false** and
the branches have genuinely diverged. A trial merge is nonetheless clean:

```bash
git merge-tree --write-tree origin/staging origin/main
```

exits `0` and writes a tree with no conflict markers. Both commits are
`chrome-extension/` and `.github/` changes that `staging` has not touched in a
conflicting way.

**Re-run both checks immediately before opening the pull request**, because
`main` receives hotfixes and the answer has a shelf life of days:

```bash
git fetch origin
git merge-base --is-ancestor origin/main origin/staging \
  && echo "no divergence" || echo "diverged, run the trial merge"
git merge-tree --write-tree origin/staging origin/main | head -20
```

Conflict markers in that output mean the promotion pull request will open
conflicting, and the fix is a separate pull request into `staging` that merges
`main` back first, reviewed on its own. Do not resolve a conflict inside the
promotion pull request.

### 3. Route 53 record writes: production is not exposed the way Portfolio was

Portfolio's first apply errored on three SES DKIM CNAMEs, because the
cross-account Route 53 role in the management account carried no
`route53:ChangeResourceRecordSets` on the zone. That is a real failure mode and
it is worth checking here rather than assuming the estates match. They do not.

CarModPicker production **owns its own zone**. `carmodpicker.com.` is
`Z03899387GZ4WUAWPP7H`, a public hosted zone with 16 record sets, held directly
in 734702670403. The production run role,
`arn:aws:iam::734702670403:role/CarModPicker-Terraform`, carries
`AdministratorAccess` with no inline policies and writes records in its own
account with full `route53:*`. There is no cross-account assume in the
production path at all.

The scoped delegation role does exist, but it is staging's:
`WebbPulse-CarModPicker-staging-Route53-Delegation` is assumed by the staging
run role and its `ChangeResourceRecordSets` is limited to record types `NS` and
`DS` on names matching `staging.carmodpicker.com`. That role could not create a
DKIM CNAME, which is exactly Portfolio's failure, and it is not in this
promotion's path.

Production already carries three `*._domainkey.carmodpicker.com` CNAMEs, a
`_dmarc` TXT, `bounce.carmodpicker.com` MX and TXT, and two ACM validation
CNAMEs. **So SES DKIM is already verified in production**, which is the other
half of why Portfolio's failure does not repeat: there are no DKIM records left
to create.

**Not a blocker.** Verify the conclusion rather than the reasoning at step 3,
by reading the plan for any `aws_route53_record` create.

### 4. DMARC: no Portfolio-style hazard here

Portfolio's hard no-go was `aws_route53_record.ses_dmarc` overwriting the
production DMARC record, because a resource its own comment called staging-only
was gated on something that was true in both environments.

CarModPicker has no such resource. `terraform/ses.tf` creates no DMARC record at
all. The one DMARC record in this configuration is
`aws_route53_record.dmarc` in `terraform/route53.tf`, it is gated on
`local.custom_domain`, and it is **byte identical on `main` and on `staging`**:

```hcl
resource "aws_route53_record" "dmarc" {
  count   = local.custom_domain ? 1 : 0
  zone_id = module.staging_dns.zone_id
  name    = "_dmarc.${local.domain_name}"
  type    = "TXT"
  ttl     = 60
  records = ["v=DMARC1; p=none;"]
}
```

It is already in production state and already applied. The promotion does not
change it. **Not a blocker**, and the step 3 gate that reads "no change to any
Route 53 record" covers it anyway.

### 5. SES is in the production sandbox, and the access request was denied

`aws sesv2 get-account` in 734702670403 returns `ProductionAccessEnabled:
false`, a 200 message daily cap and a 1 message per second rate.
`EnforcementStatus` is `HEALTHY`. Two identities are verified for sending:
`carmodpicker.com` as a domain and `tyler@webbpulse.com` as an address.

In the sandbox SES delivers only to addresses or domains that are themselves
verified in the account. So after promotion, email verification and password
reset links reach those two identities and nothing else. Every other recipient
gets a rejected send.

**This is materially worse for CarModPicker than it was for Portfolio.**
Portfolio is a single administrator product with registration disabled, so
nothing in it mails a stranger. CarModPicker has 174 real users and a
self-service signup. Password reset by email does not work for any of them
while the account is in the sandbox.

A production access request for this account was already made and **denied**,
case 178824163700078. The likely cause recorded at the time was that the
sending domain was not DKIM-verified when the request went in; it is verified
now, so an appeal has a better case than the original request did. An appeal
needs a reply on the existing case.

**This is the owner's out-of-band item and it is noted here as a known
limitation only.** No support case is opened by this runbook and none should be
opened without the owner saying so first. Opening one, or appealing the denied
one, is an owner decision.

What it means for the promotion: the identity path's password and OAuth sign-in
work regardless, because none of them sends mail. Email verification and
password reset are degraded for the 174 users in exactly the way they already
are today, since the monolith sends through the same sandboxed account. **The
promotion does not make this worse and does not fix it.** Proceed knowingly.

### 6. `bootstrap_image_tag` freshness

`var.bootstrap_image_tag` seeds `image_uri` for each per-domain function and is
validated against `^sha-[0-9a-f]{40}$`. Lambda pulls and optimises the image
when it **creates** the function, so a tag that does not resolve fails the
create. `image_uri` is on the module's `ignore_changes` list, so the deploy
step's `UpdateFunctionCode` is not undone by the next plan and the value never
needs changing again once the function exists.

This promotion **creates four new functions**: `build-lists`, `catalog`,
`identity` and `users`. So the seed is squarely on the create path, which is
the case the ECR lifecycle gotcha bites.

`ecr.tf` expires untagged images after a day and keeps only the last ten tagged
`sha-` images per repository. Deploy Backend builds all nine domain images on
every push, so ten pushes is roughly ten merges and the window is short. Row
20's apply on staging failed exactly this way, on a tag still pointing at row
14's commit, and a speculative plan cannot detect it: the plan renders the image
URI as a string and only `CreateFunction` resolves it, so the run is green and
the apply fails partway through.

Today's value on the production workspace is
`sha-51d573a3a2d987ad3b3915c632f1cd394f85e672` and it is **present in all nine
repositories**, pushed 2026-09-09. So it is fine as of this writing.

It will not stay fine. **Refresh it to the sha of the promotion merge commit
before confirming the first apply**, after Deploy Backend has pushed images for
that sha, and confirm the tag resolves in each of the four repositories whose
function is being created:

```bash
export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
SHA=sha-<promotion merge sha>
for d in build-lists catalog identity users; do
  printf '%-12s ' "$d"
  aws ecr describe-images --repository-name "carmodpicker-production/$d" \
    --image-ids "imageTag=$SHA" --query 'imageDetails[].imagePushedAt' --output text \
    || echo MISSING
done
```

This is why step 2 dispatches Deploy Backend before the first apply rather than
after it, which is the opposite of Portfolio's order and is the one structural
difference between the two runbooks.

### 7. The Chrome extension publishes on merge, and the locked decision says when

> **FIXED, 2026-09-10, by CarModPicker PR 415.** The push trigger is now gated on
> a variable that is deliberately unset, so **the merge no longer publishes**.
>
> `.github/workflows/chrome-extension-deploy.yml` gained a first job, `gate`,
> which reads the `production` environment variable
> **`CHROME_EXTENSION_AUTO_RELEASE`**. `changes` and `release` both require
> `gate.outputs.allowed == 'true'`. A push releases only when that variable is
> exactly `true`; `workflow_dispatch` is never gated, because a manual run is
> already an explicit decision to release.
>
> The variable was **not created**, and an unset variable reads as an empty
> string, so the hold is the default and nobody has to remember to apply it. A
> held run still appears in the run list with `gate` green and `release` skipped,
> and `gate`'s job summary says why and how to release, so a hold is visible
> rather than looking like a workflow that never triggered.
>
> This makes order 1 and order 2 below the same decision rather than a fork:
> `chrome-extension/` can ship in the promotion without burning the release, and
> the single publish happens at step 12 when the operator flips the variable.
> **Order 1's revert is no longer necessary.**

`.github/workflows/chrome-extension-deploy.yml` triggers on pushes to `main`
under `chrome-extension/**`. The promotion diff touches six files there,
including `background.ts`, `auth-callback.ts` and `options.tsx`, so before the
gate landed **the merge fired a Chrome Web Store publish**. That is live and
irreversible.

The locked decision of 2026-09-11 is: publish the extension **after the
production cutover, with the identity default flipped in the same release.**
The extension ships one artifact to the store and has no build-time environment
plumbing, so its equivalent of `VITE_AUTH_MODE` is a runtime setting in
`chrome.storage.sync` under `authMode`, read by `getAuthMode()` in
`background.ts`, with `DEFAULT_AUTH_MODE` currently `"legacy"`.

Two consequences, and they pull in opposite directions:

- The merge publishes an extension whose default is still `legacy`. That is
  safe, and it is the shape an existing install expects.
- But it burns the release. Flipping `DEFAULT_AUTH_MODE` to `"identity"` later
  is a second store publish and a second review, which is exactly what the
  locked decision says to avoid.

**So the decision to take before the merge was whether `chrome-extension/` ships
in the promotion at all.** Two workable orders, both now reachable without a
revert because the gate holds the publish either way:

1. **Revert `chrome-extension/` out of the promotion branch**, promote the
   backend and frontend, complete the cutover through step 11, then land the
   extension with `DEFAULT_AUTH_MODE = "identity"` as its own pull request to
   `main`. One store publish, correct default, matches the locked decision.
2. **Let it publish on the merge** with `legacy` default, and accept a second
   publish at step 12 for the flip. Two reviews, and the first one ships a
   default that is wrong within a day.

**Recommendation: order 1's outcome, reached the cheap way.** With the gate in
place, let `chrome-extension/` ride the promotion merge with
`CHROME_EXTENSION_AUTO_RELEASE` unset. The merge publishes nothing. Then flip
`DEFAULT_AUTH_MODE` to `"identity"` and publish once at step 12. One store
publish, correct default, matches the locked decision, and no revert to carry
and re-land.

Also confirm before merging that `main` still carries the fixed workflow, the
one that derives the version from the last `chrome-extension-v*` tag and opens a
bookkeeping pull request rather than pushing a version bump straight to `main`.
The `main-protection` ruleset blocks a direct push and the old workflow failed
that way with `GH013`.

### 8. Google brand verification: done, not a blocker

Google brand verification for the CarModPicker production OAuth client was
submitted and **verified and published** on 2026-09-11; the domain was already
verified in Search Console. The consent screen is in production rather than
testing.

One thing still worth a look before real users exercise OAuth: consent screen
changes can take a few hours to take effect, and a screen left in testing admits
only listed test users. Confirm the publishing status reads "In production" in
the console before step 9's verification, not after.

The registered redirect URI is compared by **exact string equality**, not by
prefix. The string this configuration will send is derived in `identity.tf`
from `local.identity_issuer`:

```
https://api.carmodpicker.com/api/auth/oauth/callback
```

Confirm that exact string is registered on both the Google client and the
GitHub OAuth app. A mismatch fails the callback rather than the authorize, so it
presents late and looks like a broken sign-in rather than a misconfiguration.

## HCP variables to add to the production workspace

Read from `ws-oh1VvpTBPxmcrSYD` on 2026-09-10. Present today:

`adopt_spans_log_group`, `aws_region`, `bootstrap_image_tag`, `environment`,
`oauth_github_client_id`, `oauth_github_client_secret`,
`oauth_google_client_id`, `oauth_google_client_secret`, `secret_key`,
`sentry_dsn`, and the three `TFC_AWS_*` environment variables.

**Nothing has to be added for the first apply.** Every variable the identity
stack needs in production either already exists or has a correct default. The
table below is the full set that differs from staging, with the production
answer for each and the description text to paste when one is created.

| Variable | Add to production? | Value | Description to use | Why |
| --- | --- | --- | --- | --- |
| `identity_jwt_mode` | **Yes, but only at step 8** | `native` | `Native API Gateway JWT authorizer. Requires the identity function to be deployed and already serving discovery and JWKS at the production API host, because CreateAuthorizer fetches both synchronously at create time.` | Absent means `off`, which is right for the first apply. Adding it as `native` before the identity function serves discovery fails the apply. |
| `domain_jwt_enforced` | **Yes, but only at step 11** | `true` | `Require an identity access token at the gateway on the 80 domain route keys that need an authenticated caller. Flip to true only after the frontend sends identity tokens; the keys exist and are inert either way.` | Defaults `false`. Marking the keys before the frontend cutover signs every user out of every write path. |
| `passkeys_enabled` | Optional, later | `true` | `Mount the package's seven passkey routes on the identity function.` | Defaults `false` in this repository, deliberately, as a staged rollout switch. Staging has it `true`. Leave unset for the promotion. |
| `passkeys_passwordless` | Optional, later | `true` | `Allow a passkey to be a first factor.` | Defaults `false`. Leave unset; turning it on makes a passkey a way in with no password. |
| `parent_route53_zone_id`, `route53_write_role_arn` | No | n/a | n/a | Staging-only. Their validations are conditioned on `var.environment == "staging"`, and production owns its zone directly. |
| `staging_access_gate`, `staging_access_users`, `staging_profile` | No | n/a | n/a | Staging-only. `staging_profile` must stay at its default `full`. |
| `gcp_project_id`, `TFC_GCP_*` | No | n/a | n/a | Staging multi-cloud only. |
| `extension_api_key` | Owner decision | n/a | n/a | Unset in both environments. Empty means API-key auth is disabled and only an admin bearer token is accepted on the batch price-history route. Unrelated to this promotion. |

The two passkey flags are the one place production's defaults differ from
staging's behaviour in a way that changes what "verified" means at the end.
With both unset, the passkey routes are not declared in production and **passkey
sign-in cannot be part of the production verification**. That is expected, not a
fault, and turning them on is a separate decision after the promotion holds.

### Secret keys

The `carmodpicker-production/app` secret already exists. After promotion,
`module.app_secrets` adds two keys to that JSON blob, matching staging:

| Key | Source | Present in production today |
| --- | --- | --- |
| `SECRET_KEY` | `var.secret_key` | yes |
| `SENTRY_DSN` | `var.sentry_dsn` | yes |
| `OAUTH_GOOGLE_CLIENT_SECRET` | `var.oauth_google_client_secret` | **added by the promotion apply** |
| `OAUTH_GITHUB_CLIENT_SECRET` | `var.oauth_github_client_secret` | **added by the promotion apply** |

Both source variables already exist on the workspace as sensitive values, so the
apply fills them rather than writing empty strings. The key names are upper case
on both sides and the case is load bearing.

**Never read the secret's value to check this.** Verify the shape from the plan
and from behaviour, which is what step 9 does with
`GET /api/auth/oauth/providers`. `describe-secret` metadata is fine;
`get-secret-value` is not, and a promotion agent called it on the Portfolio
equivalent despite the rule, which is recorded as an incident.

## Why this is three applies and not one

Portfolio's promotion was two applies. This one is three, because row 12 adds a
step Portfolio did not have.

1. **First apply, `identity_jwt_mode` absent, `domain_jwt_enforced` absent.**
   Creates the four remaining domain functions and their route cuts, the two
   KMS keys, the ten identity tables, the IAM grants, the SES grant, row 8's
   fifteen `/api/auth` route keys, row 12a's eighty domain keys plus two guard
   keys, and the `IDENTITY_*` environment on the identity function. It also
   retires the monolith, `$default` and the zip chain. No authorizer is
   created. Nothing is enforced at the gateway, and the identity function
   verifies tokens itself in every mode.
2. **Second apply, `identity_jwt_mode = "native"`.** Now `CreateAuthorizer` can
   fetch discovery and JWKS, and the fifteen marked `/api/auth` routes move to
   `authorization_type = JWT`. Those routes are **replaced** rather than
   updated, because the platform module keeps them in a separate resource so
   the `.well-known` routes exist before the authorizer and the protected
   routes after it.
3. **Third apply, `domain_jwt_enforced = true`.** The eighty domain keys gain
   `require_identity_jwt` and move to the JWT authorizer too.

The first two are forced by `CreateAuthorizer`, which **synchronously fetches**
`https://api.carmodpicker.com/api/auth/.well-known/openid-configuration` from
outside AWS and then the JWKS it names, at create time. Today that URL returns
`404`, confirmed live. Attempting both in one apply fails the second half and
leaves the workspace mid-apply. The variable's own description says the same
thing.

The third is forced by the frontend. Until the deployed bundle sends identity
access tokens, marking the domain keys makes the gateway reject every
authenticated write from every one of the 174 users.

## The checklist

### Step 0. Gates before anything

- [ ] **Blocker 1 is fixed and a production speculative plan renders.** Not
      "should render": a run that reached `planned_and_finished` with a diff.
- [ ] The divergence check and trial merge from blocker 2 were re-run today and
      the merge is clean.
- [ ] The owner has decided on the Chrome extension, blocker 7: reverted out of
      the promotion, or publishing on the merge with a second publish accepted.
- [ ] The owner has accepted the SES sandbox limitation, blocker 5, knowing it
      affects password reset for 174 real users.
- [ ] The Google and GitHub OAuth apps carry
      `https://api.carmodpicker.com/api/auth/oauth/callback` exactly, and the
      Google consent screen reads "In production".
- [ ] Staging has been confirmed working on the identity path.
- [ ] The owner is present. **Every commit to `main` auto-deploys**, so the
      merge in step 2 is a release.

**No-go if any box is unchecked.**

### Step 1. Take a restore point

```bash
cd /home/tyler-webb/Documents/Github/WebbPulse/CarModPicker
git fetch origin
git rev-parse origin/main
```

Record that sha. It is the revert target in the rollback section, and it is the
only cheap part of the rollback.

Snapshot the users table, because step 6 writes derived from it and step 12
eventually clears from it:

```bash
AWS_PROFILE=CarModPicker-Production/AdministratorAccess \
  aws dynamodb scan --region us-west-2 \
    --table-name carmodpicker-production-users \
    > ~/cmp-prod-users-preflight.json
```

Confirm the count matches what the table reports, without printing any row:

```bash
jq '.Count' ~/cmp-prod-users-preflight.json   # expect 174
```

**That file contains 174 real bcrypt hashes and 174 plaintext TOTP seeds.** Keep
it off shared storage, do not open it, do not print any column from it, and
delete it when the promotion holds. `jq '.Count'` is the only thing that should
ever read it other than a restore.

Also record the workspace's current variable state, so a rollback knows what to
put back:

```bash
T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
curl -s -H "Authorization: Bearer $T" \
  https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars \
  | jq -r '.data[] | select(.attributes.sensitive == false)
           | "\(.attributes.key)=\(.attributes.value)"'
```

### Step 2. Merge, then push images, then refresh the bootstrap tag

**Confirm production is on mode off first.** Re-verify rather than trusting this
document:

```bash
T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
curl -s -H "Authorization: Bearer $T" \
  https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars \
  | jq -r '.data[].attributes | select(.key=="identity_jwt_mode" or .key=="domain_jwt_enforced")
           | "\(.key)=\(.value)"'
```

Expect no output. **If it prints `identity_jwt_mode=native`, stop:** the merge
would trigger a run that fails at `CreateAuthorizer`.

Then open the promotion pull request from `staging` into `main` and merge it.
**CarModPicker uses squash merges**, so this is `--squash`, which is a
difference from Portfolio and matters because the merge commit sha is what the
bootstrap tag will be set to:

```bash
gh pr create --base main --head staging \
  --title "Promote the identity adoption and rows 25 to 32 to production" \
  --body "..." --repo WebbPulse/CarModPicker
gh pr merge <n> --squash --repo WebbPulse/CarModPicker
MERGE_SHA=$(git fetch origin && git rev-parse origin/main)
echo "$MERGE_SHA"
```

Merging is an owner action.

**Now let Deploy Backend finish before touching the workspace.** The merge fires
`deploy-backend.yml` on `main`, which builds and pushes all nine domain images
tagged `sha-$MERGE_SHA`:

```bash
gh run list --branch main --workflow deploy-backend.yml --limit 3 --repo WebbPulse/CarModPicker
gh run watch <run-id> --repo WebbPulse/CarModPicker
```

That run will partly fail, and it is expected to. `deploy-images` calls
`UpdateFunctionCode` on functions that do not exist yet for `build-lists`,
`catalog`, `identity` and `users`, and `verify-route-cuts` probes prefixes that
are not cut. The `existing-functions` job is what scopes the deploy to what
exists. **The only thing that must succeed is `build-images`**, because the
images are what the first apply creates the functions from. Confirm that job
green and read the rest as informational.

Then confirm the tag actually landed in all four new repositories and set it:

```bash
export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
for d in build-lists catalog identity users media build-logs moderation vehicles admin; do
  printf '%-12s ' "$d"
  aws ecr describe-images --repository-name "carmodpicker-production/$d" \
    --image-ids "imageTag=sha-$MERGE_SHA" \
    --query 'imageDetails[0].imagePushedAt' --output text 2>/dev/null || echo MISSING
done
```

**Gate: all nine print a timestamp.** A `MISSING` here means the first apply
fails partway through at `CreateFunction`, with the role, the X-Ray policy and
the log group already created, which is a messy but recoverable state. Do not
proceed on a `MISSING`.

Then PATCH the workspace variable:

```bash
T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
VAR_ID=$(curl -s -H "Authorization: Bearer $T" \
  https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars \
  | jq -r '.data[] | select(.attributes.key=="bootstrap_image_tag") | .id')
curl -s -X PATCH -H "Authorization: Bearer $T" \
  -H "Content-Type: application/vnd.api+json" \
  -d "{\"data\":{\"id\":\"$VAR_ID\",\"type\":\"vars\",\"attributes\":{\"value\":\"sha-$MERGE_SHA\"}}}" \
  "https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars/$VAR_ID" \
  | jq -r '.data.attributes | "\(.key)=\(.value)"'
```

### Step 3. The first apply, mode off

**Blocker 1 is fixed, so this plan renders.** It did not before: through module
`2.9` the identity role policies counted off a value that is unknown while the
identity role is still to be created, and the run reached `errored` with
`Invalid count argument` before showing any diff. `platform-modules` `v2.10.0`
plus CarModPicker PR 415 moved those counts onto `attach_role_policies`, and a
speculative plan against this workspace now reaches `planned_and_finished` with
**201 to add, 6 to change, 18 to destroy** for the branch as it stood at the fix,
and every hard stop in the table below passes on it. The 18 destroys are row 32's
retirement, listed in this table's last two rows, and nothing else. Section 1 has
the mechanism and the run ids. If a run here still errors on a count, the module
pin in `terraform/identity.tf` is the first thing to read: it must be `~> 2.10`
or later.

The merge queued a run on `ws-oh1VvpTBPxmcrSYD` before the tag was refreshed, so
**discard it and queue a fresh one** rather than confirming a run planned
against the stale tag:

```bash
T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
curl -s -H "Authorization: Bearer $T" \
  "https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/runs?page%5Bsize%5D=1" \
  | jq -r '.data[0] | {id, status: .attributes.status}'
```

No workspace auto-applies, so confirm the apply through the UI or the API after
reading the plan.

**What the plan should contain.** Derived from the branch diff and from what
production is missing today. Treat the counts as shapes to check, not as a
number to match, and read every destroy line.

| Group | Expect | Note |
| --- | --- | --- |
| Domain functions | 4 create, each with role, log group, X-Ray policy and runtime policy | `build-lists`, `catalog`, `identity`, `users` |
| KMS keys, aliases, key policies | 2 keys, 2 aliases, 2 policies | `identity-signing` and `identity-mfa`. Portfolio's runbook under-counted this by one because it forgot the MFA key; it is created here by the module default |
| Identity tables | 10 create | `credentials`, `refresh-tokens`, `login-attempts`, `identity-tokens`, `totp-factors`, `recovery-codes`, `passkeys`, `webauthn-challenges`, `oauth-states`, `oauth-links`. All carry `deletion_protection = true` because `var.environment == "production"` |
| IAM role policies on the identity role | 3 create | `identity-signing`, `identity-tables`, `identity-mfa`. These are the three that blocker 1 was about. They plan as creates now because their `count` reads `attach_role_policies`, not the role id |
| Gateway routes, row 8 | 15 create | The explicit `/api/auth` keys, `authorization_type` NONE in this apply |
| Gateway routes, row 12a | 82 create | 80 domain keys plus 2 anonymous guard keys, all unmarked |
| Gateway routes, domain cuts | 8 create | The `ANY` bare and `{proxy+}` pair for each of four new prefixes |
| Gateway authorizer | **0** | Mode is `off`. Any `aws_apigatewayv2_authorizer` in this plan is wrong. **Hard stop.** |
| Identity Lambda environment | included in its create | The `IDENTITY_*` block |
| `carmodpicker-production/app` secret version | 1 change, or 1 create plus 1 destroy | The two `OAUTH_*_CLIENT_SECRET` keys. A secret version showing as add plus destroy is normal |
| Route 53 records | **0 changes** | DKIM and DMARC already exist and are unchanged between branches. Any create here wants reading before applying |
| Monolith retirement, row 32 | destroys | `carmodpicker-production-api`, `$default`, the artifacts bucket and the zip chain. **These destroys are expected and are the point of row 32** |
| Destroys of any DynamoDB table | **expect none** | A destroy of a data table here is a stop |

Because production has none of the identity stack, every address in
`identity.tf` is a plain create and there is nothing to move. `identity.tf`'s
own comment says a destroy anywhere in that module's plan means an address did
not line up and must be investigated rather than applied.

**Gate:** the plan contains no destroy of any DynamoDB table, no authorizer, and
no Route 53 record change. The only destroys are row 32's monolith retirement,
and the owner recognises each one. Otherwise do not apply.

Apply, and wait for `applied`.

**If the apply errors partway through**, read which resources landed before
deciding anything. Portfolio's first apply errored on three DKIM CNAMEs with 58
of 61 resources applied, and the right response was to continue rather than to
roll back, because every hard-stop gate had passed and the failure blocked
nothing downstream. A retry plan after a partial apply is simply the remainder
and needs no state surgery.

### Step 4. Verify the first apply landed

```bash
export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2

aws dynamodb list-tables \
  | jq -r '.TableNames[] | select(test("credentials|refresh-tokens|login-attempts|identity-tokens|totp-factors|recovery-codes|passkeys|webauthn-challenges|oauth-states|oauth-links"))'

aws kms list-aliases --query "Aliases[?contains(AliasName,'identity')].AliasName"

aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `carmodpicker-production`)].FunctionName' \
  --output text | tr '\t' '\n' | sort
```

Expect the ten identity tables, two aliases
(`alias/carmodpicker-production-identity-signing` and `-identity-mfa`), and the
nine domain functions. The `carmodpicker-production-api` monolith should be
gone.

Confirm the route count moved as planned:

```bash
API=$(aws apigatewayv2 get-apis \
  --query "Items[?Name=='carmodpicker-production-api'].ApiId" --output text)
aws apigatewayv2 get-routes --api-id "$API" --max-results 500 \
  --query 'length(Items)'
aws apigatewayv2 get-authorizers --api-id "$API" --query 'length(Items)'
```

Expect a route count in the low hundreds and **`0` authorizers**. Production had
23 routes and no authorizer before this apply.

### Step 5. Deploy the backend so the identity function serves discovery

The Terraform apply created the functions from the bootstrap tag, which is the
right image, but `deploy-backend.yml` is what owns the image afterwards and what
runs `verify-route-cuts` against the new prefixes. Dispatch a fresh run rather
than re-running the step 2 one: **a re-run reuses the old reusable-workflow
ref.**

```bash
gh workflow run deploy-backend.yml --ref main --repo WebbPulse/CarModPicker
gh run watch <run-id> --repo WebbPulse/CarModPicker
```

The chain is `resolve-env`, `build-images`, `image-map`, `existing-functions`,
`deploy-images`, `smoke-domains`, `verify-route-cuts`. `resolve-env` binds the
`production` GitHub Environment from `github.ref_name == 'main'`.

This run should be fully green, unlike step 2's. `verify-route-cuts` hardcodes
the domain list and probes each prefix, so it is the check that the functions
and their routes landed together.

Then confirm the identity function carries its environment:

```bash
aws lambda get-function-configuration \
  --function-name carmodpicker-production-identity \
  --query '{Modified:LastModified,Env:keys(Environment.Variables)}'
```

`Env` must list the `IDENTITY_*` keys, including `IDENTITY_ISSUER`,
`IDENTITY_AUDIENCE`, `IDENTITY_SIGNING_KEY_ARNS`, `IDENTITY_DATA_KEY_ARN`,
`IDENTITY_COOKIE_DOMAIN` and `IDENTITY_RP_ID`.

### Step 6. Gate: discovery and JWKS must serve before mode native

This is the gate the multi-apply constraint exists for.

```bash
curl -s https://api.carmodpicker.com/api/auth/.well-known/openid-configuration | jq .
curl -s -o /dev/null -w "%{http_code}\n" \
  https://api.carmodpicker.com/api/auth/.well-known/jwks.json
```

Required:

- Both return `200`. Today both return `404`.
- `issuer` is exactly `https://api.carmodpicker.com/api/auth`, **with the
  path**. The issuer carries its path; a bare host is wrong and
  `identity.tf`'s comment on `local.identity_issuer` explains why the string is
  derived once and read from that local everywhere.
- `jwks_uri` is exactly
  `https://api.carmodpicker.com/api/auth/.well-known/jwks.json`.
- The JWKS body contains at least one **RSA** key. The authorizer is RSA only;
  it does not accept EC.

**No-go if any of these fail.** Setting `identity_jwt_mode = native` against a
`404` fails `CreateAuthorizer` and fails the apply.

### Step 7. Migrate the 174 credentials

**Portfolio's step 7 refused, and the reason does not exist here.** Its
identity-aware admin seeder wrote a credential on the identity function's first
cold start, 48 seconds after the backend deploy and therefore before the
migration ever ran. Both hashes verified the same password and differed only
because bcrypt salts each one, and both scripts compare hash strings for
equality, so the migration reported a conflict on a benign difference and needed
`--replace`.

**CarModPicker has no admin seeder.** There is no `ADMIN_USERNAME`,
`ADMIN_PASSWORD` or `ADMIN_EMAIL` anywhere in this repository, in Terraform or
in the backend, and nothing writes an identity credential at cold start. So the
ordering gap that produced Portfolio's conflict is structurally absent here and
**a conflict on this run is not expected and is not benign.**

Dry run first. The script is dry run by default and `--apply` is what writes.

```bash
cd backend
AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2 \
  python scripts/migrate_credentials_to_identity.py --prefix carmodpicker-production
```

`--prefix` selects the environment for **both** tables: it is written back into
`DYNAMODB_TABLE_PREFIX` inside `parse_args`, because the legacy users repository
reads that setting rather than the flag and would otherwise hit
`carmodpicker-development-users`.

Expect, across 174 rows:

- a `write` count for every row carrying a bcrypt `hashed_password`,
- a substantial `skip_oauth_only` count for the Google-only accounts, which have
  no hash to copy and need no credential row,
- `unchanged` zero on a first run,
- `conflict` **zero**,
- `skip` **zero**.

**Gate: zero conflicts and zero unsupported hashes.** A row whose hash is not a
bcrypt modular crypt string is reported and skipped rather than written as a
credential that could never verify, and that is a stop rather than a warning.

**If a conflict does appear**, it means something wrote an identity credential
before this ran, and since no seeder exists that is an unexplained write into
production auth data. Do not reach for `--replace` to clear it. `--replace` is
correct only when the two rows are known to be the same account with the same
password differing only by bcrypt salt, and the way to know that is to compare
the usernames on both rows and confirm they match before overriding anything.
Even then, scope the reasoning to the specific rows named in the error and
confirm with the owner. Portfolio's `--replace` was justified because a known
seeder had written a known row; a conflict here has no such explanation and
wants a person before it wants a flag.

Then write:

```bash
AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2 \
  python scripts/migrate_credentials_to_identity.py --prefix carmodpicker-production --apply
```

The script is idempotent. A rerun leaves an identical credential untouched,
`created_at` included. A differing credential is a conflict and a non-zero exit
rather than an overwrite. **Do not pass `--replace` on a first run.**

The hashes copy verbatim: both sides are `webbpulse.security.hash_password`,
bcrypt cost 12, with the same 72 byte truncation on hash and on verify. **No
user resets a password and nobody is signed out.**

### Step 8. Migrate and verify the TOTP seeds

The other half of row 7, and the one that decides whether a user with an
authenticator app can still sign in after the cutover.

```bash
cd backend
export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
P=--prefix=carmodpicker-production

python scripts/migrate_totp_seeds_to_identity.py $P            # dry run
python scripts/migrate_totp_seeds_to_identity.py $P --apply    # seal
python scripts/migrate_totp_seeds_to_identity.py $P --verify   # read only gate
```

Sealing generates a fresh AES-256 data key from KMS under
`IDENTITY_DATA_KEY_ARN`, encrypts the seed locally with AES-256-GCM and stores
the ciphertext, the nonce and the wrapped key. The encryption context is
`{"user_id": <id>, "purpose": "totp"}` and KMS binds it into the wrapped key as
authenticated data, so a ciphertext copied into another user's row fails to
decrypt rather than authenticating the wrong person.

**The seed is unchanged, so no authenticator is re-enrolled.** Same base32
bytes, same RFC 6238 defaults. Nobody rescans a QR code.

**`--apply` deliberately leaves the plaintext on the user row.** Clearing it is a
separate `--clear-plaintext` pass and it belongs on the far side of the soak, at
step 12, because it is the irreversible half.

**Gate: `--verify` exits zero.** It opens every sealed row back through
`EnvelopeCipher` and checks it, writing nothing, and exits non-zero if anything
is missing, unreadable or mismatched. Step 12 must not run unless this passed.

### Step 9. Second apply, mode native

Add the variable to the production workspace. This is an owner action in the HCP
UI, or:

```bash
T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
curl -s -X POST -H "Authorization: Bearer $T" \
  -H "Content-Type: application/vnd.api+json" \
  -d '{"data":{"type":"vars","attributes":{
        "key":"identity_jwt_mode","value":"native","category":"terraform","sensitive":false,
        "description":"Native API Gateway JWT authorizer. Requires the identity function to be deployed and already serving discovery and JWKS at the production API host, because CreateAuthorizer fetches both synchronously at create time."}}}' \
  https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars
```

The validation in `variables.tf` refuses `native` when `environment` is
`staging`, so this is only ever valid here.

Queue a run. **What this plan should contain:**

| Group | Expect |
| --- | --- |
| `aws_apigatewayv2_authorizer` | 1 create, type `JWT`, issuer `https://api.carmodpicker.com/api/auth`, audience `carmodpicker-production-api` |
| Row 8's marked routes | **15 replacements**, not updates. Every key in `local.identity_jwt_route_keys` carries `require_identity_jwt = true`, so all fifteen move into the module's separate JWT route resource |
| Row 12a's 80 domain keys | **unchanged.** `var.domain_jwt_enforced` is still `false`, so none of them carries the flag and none moves |
| The 2 anonymous guard keys | **unchanged**, and never marked |
| `.well-known` routes | **unchanged.** They must stay anonymous, since the authorizer fetches them |
| Generated `ANY` prefix pairs | **unchanged** |
| Everything else | no change |

Route replacement is briefly disruptive on those fifteen routes. It is seconds,
and they are the authenticated identity-management routes rather than the public
catalogue.

**Gate: the plan replaces exactly the fifteen routes that carry
`require_identity_jwt`, touches neither `.well-known` route, and moves none of
the eighty domain keys.** Verify the count against
`module.api.identity_jwt_route_keys` in the plan output rather than trusting the
number here. Then apply.

If the apply fails inside `CreateAuthorizer` with a message about fetching the
discovery document, step 6's gate was passed prematurely. Set
`identity_jwt_mode` back to `off`, apply to clean up, and return to step 5.

### Step 10. Verify the production identity path end to end

```bash
API=https://api.carmodpicker.com

# Anonymous, must still be 200. These are outside the authorizer.
curl -s -o /dev/null -w "discovery %{http_code}\n" $API/api/auth/.well-known/openid-configuration
curl -s -o /dev/null -w "jwks      %{http_code}\n" $API/api/auth/.well-known/jwks.json

# A flagged route with no token, must be 401 and must come from the gateway.
curl -s -o /dev/null -w "no token  %{http_code}\n" -X POST $API/api/auth/logout-all

# Public reads, unchanged throughout.
curl -s -o /dev/null -w "health    %{http_code}\n" $API/health
curl -s -o /dev/null -w "makes     %{http_code}\n" $API/api/car-makes
curl -s -o /dev/null -w "search    %{http_code}\n" $API/api/search
```

Expect `200, 200, 401, 200, 200, 200`. The last three are the regression check:
they are `200` today and must stay `200`.

Distinguishing a gateway 401 from an application 401 matters, because only the
first proves the authorizer is doing anything. Both read as 401 from a
token-less probe. Tell them apart by `integrationLatency` in the access logs: a
`-` means the request was denied before the function was invoked.

Confirm the OAuth providers are advertised, which is the behavioural check that
the two secret keys landed in the app secret:

```bash
curl -s $API/api/auth/oauth/providers | jq .
```

Expect both `google` and `github`. An empty list means a client id or secret is
missing or misspelled, since a provider is counted only when it carries a client
id and the secret lookup is a plain dict get with no error on a miss. **Never
call `get-secret-value` to check this.**

Then a real sign-in, with a real account's own password:

```bash
curl -s -X POST $API/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"<user>","password":"<password>"}' \
  | jq '{has_access: (.access_token != null), token_type}'
```

Do not paste a password into a shared transcript. Then call a flagged route with
the returned access token and expect `200` rather than `401`.

A wrong password must be refused:

```bash
curl -s -o /dev/null -w "bad pw    %{http_code}\n" -X POST $API/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"<user>","password":"definitely-not-the-password"}'
```

Expect `401`. A `200` here means the credential comparison is not doing what it
should and is an immediate stop.

Passkey routes will not be present, because `passkeys_enabled` defaults `false`
in production. That is expected.

**Gate:** password sign-in works through `/api/auth/login`, a flagged route
accepts the token and refuses a missing one, a wrong password is 401, the OAuth
providers list has two entries, and the public reads are unchanged. Otherwise
roll back before touching the frontend.

### Step 11. Flip the frontend, then enforce the domain routes

The production GitHub Environment has **no `AUTH_MODE` variable**, and neither
does staging. `VITE_AUTH_MODE` defaults to `bearer` when absent, which is what
both environments build today.

```bash
gh variable set AUTH_MODE --env production --body identity \
  --repo WebbPulse/CarModPicker
gh workflow run frontend-deploy.yml --ref main --repo WebbPulse/CarModPicker
gh run watch <run-id> --repo WebbPulse/CarModPicker
```

`CODEARTIFACT_DOMAIN_OWNER` is set at repository level (`432410731887`), so it
resolves for the production environment too. No new GitHub variable is needed
beyond `AUTH_MODE`.

Then sign in at `https://www.carmodpicker.com` in a browser as a real user, and
confirm the session survives a reload.

**Gate: a real owner sign-in through the identity path succeeds in a browser.**
Not a curl, and not a synthetic account. This gate is what steps 11b and 12 are
waiting on, and it is the one Portfolio's promotion stopped at.

**Then, and only then, the third apply.** Add the variable:

```bash
T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
curl -s -X POST -H "Authorization: Bearer $T" \
  -H "Content-Type: application/vnd.api+json" \
  -d '{"data":{"type":"vars","attributes":{
        "key":"domain_jwt_enforced","value":"true","category":"terraform","sensitive":false,
        "description":"Require an identity access token at the gateway on the 80 domain route keys that need an authenticated caller. Flip to true only after the frontend sends identity tokens; the keys exist and are inert either way."}}}' \
  https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars
```

**What this plan should contain, and why it is not Portfolio's 0/1/0.**

Portfolio's equivalent flip was `0 add, 1 change, 0 destroy`, because in `gate`
mode the platform module keeps a marked route at the same address with the same
`authorization_type` and the only diff is the gate authorizer Lambda's
environment gaining the route list. `variables.tf` says exactly that, and it is
correct **for staging**.

**Production is in `native` mode, so the shape is different.** In native mode
`module.api.identity_jwt` is non-null, and the module moves every route carrying
`require_identity_jwt` into its own resource. Flipping `domain_jwt_enforced`
marks all eighty domain keys at once, so all eighty move, and a move between
resource addresses is a replacement.

| Group | Expect |
| --- | --- |
| Domain route keys | **80 replacements**, counted against the eighty keys in `local.domain_identity_jwt_route_paths` |
| The 2 anonymous guard keys | **unchanged**, never marked |
| Row 8's 15 identity keys | **unchanged**, already on the authorizer from step 9 |
| `aws_apigatewayv2_authorizer` | **unchanged**, 1, created in step 9 |
| Generated `ANY` prefix pairs | **unchanged** |
| Everything else | no change |

So expect roughly `80 add, 0 change, 80 destroy` rendered as replacements rather
than a `0/1/0`. **Verify the count against the plan output rather than against
this table**, and confirm that the two guard keys
`GET /api/reports/count` and `GET /api/bug-reports/count` are not among them:
they hold a more specific match than the flagged `{id}` keys on the same method
and depth, and marking them would demand a token on an anonymous count route.

Eighty route replacements is briefly disruptive across every authenticated write
path. It is seconds per route and they are not replaced atomically, so run this
apply at a quiet hour rather than alongside the frontend deploy.

**Gate: exactly the eighty keys move, the two guard keys do not, and the fifteen
identity keys are untouched.** Then apply.

After it lands, re-run the step 10 probes plus a write:

```bash
# an authenticated write with a valid identity token must still be 200
curl -s -o /dev/null -w "write     %{http_code}\n" -X POST $API/api/part-price-alerts \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{...}'
# and without one must be 401 from the gateway
curl -s -o /dev/null -w "write 401 %{http_code}\n" -X POST $API/api/part-price-alerts \
  -H 'Content-Type: application/json' -d '{...}'
```

Claims reach the domain functions at `requestContext.authorizer.jwt.claims` as a
**string map**: every value is a string, `exp`, `iat` and `nbf` included,
because API Gateway flattens the claim set. `identity_claims.py`'s dual-shape
reader owns that coercion. The Lambda Web Adapter forwards the request context in
`x-amzn-request-context` as **plain JSON, not base64**; a base64 decode of it
fails and presents as a 401.

### Step 12. Chrome extension, soak, then clear the plaintext

Publish the extension per the blocker 7 decision. This is the one store publish
the locked decision allows, and it carries `DEFAULT_AUTH_MODE = "identity"`.

**The release is held behind a variable, and this is where the operator flips
it.** The gate in `.github/workflows/chrome-extension-deploy.yml` releases on a
push only when the `production` environment variable

```
CHROME_EXTENSION_AUTO_RELEASE = true
```

is exactly `true`. It is unset by default, which is the hold. Until it is set, a
promotion merge that touches `chrome-extension/**` runs the workflow, reports
the hold in the `gate` job summary, and skips `release`.

So, in order:

1. Land `DEFAULT_AUTH_MODE = "identity"` on `main` in the ordinary way. With the
   variable unset this still publishes nothing, so it can land early.
2. Set the variable, as the owner or the promotion operator:

   ```bash
   gh variable set CHROME_EXTENSION_AUTO_RELEASE --body true \
     --env production --repo WebbPulse/CarModPicker
   ```

3. Release. Either re-run the held workflow run, or dispatch it manually, which
   is never gated and needs no variable at all:

   ```bash
   gh workflow run chrome-extension-deploy.yml --repo WebbPulse/CarModPicker
   ```

4. **Put the hold back once the publish is done**, so a later merge that touches
   the extension cannot spend a store review by accident:

   ```bash
   gh variable delete CHROME_EXTENSION_AUTO_RELEASE \
     --env production --repo WebbPulse/CarModPicker
   ```

   Setting it to anything other than `true` works as well; deleting it is
   tidier, because unset and held then read the same.

Then watch the run:

```bash
gh run list --branch main --workflow chrome-extension-deploy.yml --limit 3 \
  --repo WebbPulse/CarModPicker
```

A run whose `release` job shows as skipped did not publish. Read the `gate` job
summary for which of the two reasons applies, the variable or an unchanged
extension tree.

A store review is not instant and is outside anybody's control here. Existing
installs keep working through the handoff either way, because `getAuthMode()`
reads `chrome.storage.sync` and an install that has never set it falls to the
shipped default.

**Then soak.** Watch for a real working day before the irreversible step:

```bash
aws cloudwatch describe-alarms --state-value ALARM \
  --query 'MetricAlarms[].AlarmName' --output text
```

Expect empty. Watch the identity function's error rate and the gateway 4xx rate,
and give the 174 users time to sign in on their own schedule. A user who has not
signed in since the cutover has not tested anything.

**Only after the soak, and only if step 8's `--verify` exited zero**, clear the
plaintext TOTP seeds:

```bash
cd backend
export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
P=--prefix=carmodpicker-production
python scripts/migrate_totp_seeds_to_identity.py $P --clear-plaintext
python scripts/migrate_totp_seeds_to_identity.py $P --clear-plaintext --apply
```

Each row is verified again inside this pass rather than trusting the earlier
`--verify`, which is why it is safe to run and why it still refuses rather than
clearing a row it cannot open.

**This is the one-way door.** After it, the sealed seed is the only copy and
`docs/security/totp-seed-encryption.md`'s finding is closed.

Note that **CarModPicker has no `clear_legacy_credentials.py`.** Portfolio has
one and this repository does not, so clearing `hashed_password` from the users
table is not a step here. Row 13 owns retiring the legacy `/api/auth` routes and
the legacy columns, and it is a separate piece of work with its own review, not
a tail step of this promotion. Leave `hashed_password` populated: it costs
nothing, and while it is there the bearer rollback in the table below still
works.

### Step 13. Close out

- [ ] Delete `~/cmp-prod-users-preflight.json`.
- [ ] **Delete `LAMBDA_FUNCTION_NAME` and `LAMBDA_ARTIFACTS_BUCKET` from the
      `production` GitHub Environment.** Row 32 deleted `backend-deploy.yml`, the
      monolith function and the artifacts bucket, so both variables now name
      things that do not exist. Leaving them set breaks nothing and is exactly
      the kind of stale value someone later reads as a live fact. Do the same on
      `staging` if it has not been done already. `TFC_WORKSPACE_ID` and
      `TFC_API_TOKEN` stay, because `frontend-deploy.yml` still polls with them.
- [ ] Confirm `dig +short TXT _dmarc.carmodpicker.com` is unchanged.
- [ ] Confirm the CloudWatch alarms are quiet.
- [ ] Confirm `aws sesv2 get-email-identity --email-identity carmodpicker.com`
      still reports DKIM `SUCCESS`.
- [ ] Note that sending is sandbox-limited until an owner-approved support case
      says otherwise, and that the earlier request was denied.
- [ ] Decide separately on `passkeys_enabled`, on `passkeys_passwordless`, on
      appealing the SES case, and on row 13.

## Rollback

Rollback gets narrower at every step, and the honest summary is that **it is
cheap before step 7 and not cheap after step 12.**

### What reverting `main` does undo

Reverting `main` to the sha recorded in step 1 and pushing rebuilds and
redeploys the previous backend image and the previous frontend bundle. The
frontend returns to `bearer` mode once `AUTH_MODE` is also removed, and the
legacy login serves again from the monolith. That covers the application layer,
and it works **only because step 12 does not clear `hashed_password`**.

```bash
gh variable delete AUTH_MODE --env production --repo WebbPulse/CarModPicker
git revert --no-commit <promotion-merge-sha>
```

### What reverting `main` does not undo

- **The gateway authorizer and the route markings.** Both are Terraform state,
  not code deployment. Removing them means setting `domain_jwt_enforced` back
  to `false` and `identity_jwt_mode` back to `off` and applying. Until that
  apply runs, ninety-five routes keep demanding a JWT, and a reverted frontend
  that stopped sending one is locked out of every write path. **Revert the two
  variables and apply before or alongside the code revert, never after.**
- **The identity tables and the two KMS keys.** A revert of the code plans them
  for destroy, and all ten tables carry `deletion_protection = true` because
  `var.environment == "production"`. So the destroy fails rather than losing
  data, which is the safe failure, but a clean revert needs them removed from
  state or the protection lifted deliberately. Prefer leaving them: unused
  tables cost nothing and hold 174 migrated credentials.
- **The monolith retirement.** Row 32 destroys
  `carmodpicker-production-api`, `$default`, the artifacts bucket and the zip
  chain. Reverting the code plans them back as creates, but the artifacts
  bucket's objects are gone and the monolith's zip is not in a bucket any more.
  **This is the least reversible part of the infrastructure change and it is
  independent of identity.** Treat any rollback past step 3 as fix-forward on
  the domain split, whatever happens to the identity rows.
- **The cleared plaintext TOTP seeds, step 12.** Once cleared, the sealed copy
  is the only one. Recovery is restoring the column from the step 1 snapshot.
- **Anything written through the identity path after the cutover.** A password
  changed through the identity flow exists only in the `credentials` table, and
  a revert to the legacy column resurrects the old password for that user.

### The practical rollback, by step reached

| Reached | Rollback |
| --- | --- |
| Through step 2, before the first apply | Revert `main`. Nothing in AWS changed except pushed ECR images, which are harmless. Reset `bootstrap_image_tag` to its previous value. |
| Through step 6 | Revert `main` and accept that the monolith retirement is not cleanly reversible. The identity stack sits unused and harmless; leave the tables. |
| Through step 8 | As above. The migrated credentials and sealed seeds are additive and read by nothing until mode is native. Nothing has been taken away. |
| Through step 10 | Set `identity_jwt_mode` to `off`, apply, then revert `main`. The frontend was never flipped, so users are unaffected throughout. |
| Through step 11 | Set `domain_jwt_enforced` to `false` **and** `identity_jwt_mode` to `off`, apply both, delete the `AUTH_MODE` variable, redeploy the frontend. `hashed_password` is still populated so bearer login works immediately. |
| After step 12 | Restore the plaintext seeds from the step 1 snapshot before reverting, or accept that the sealed seed is the only copy and fix forward. Fixing forward is usually right here, and the extension is already published. |

## Recommended sequence, short form

1. **Fix blocker 1** so a production speculative plan renders, as a
   `platform-modules` change, and confirm a plan-only run reaches
   `planned_and_finished` with a diff.
2. Decide the Chrome extension question and, if order 1, revert
   `chrome-extension/` out of the promotion branch.
3. Squash-merge `staging` into `main` with both JWT variables absent, let Deploy
   Backend push the images, refresh `bootstrap_image_tag` to the merge sha,
   confirm the tag resolves in all nine repositories, and apply: four domain
   functions, two KMS keys, ten identity tables, 105 route keys, and the
   monolith retired. No authorizer.
4. Dispatch a fresh Deploy Backend and confirm
   `https://api.carmodpicker.com/api/auth/.well-known/openid-configuration`
   returns `200` with the path-carrying issuer.
5. Dry run then apply `migrate_credentials_to_identity.py` for all 174 rows,
   expecting zero conflicts because this product has no admin seeder; then seal
   and `--verify` the TOTP seeds.
6. Set `identity_jwt_mode = native`, apply the second run, and verify: public
   reads 200, a flagged route 401 without a token, providers lists two, wrong
   password 401.
7. Set `AUTH_MODE=identity` on the production GitHub Environment, redeploy the
   frontend, and get a **real browser sign-in from the owner**.
8. Set `domain_jwt_enforced = true`, apply the third run, expect eighty route
   replacements, and re-probe an authenticated write both ways.
9. Publish the extension with the identity default, soak for a working day, then
   `--clear-plaintext --apply`. Leave `hashed_password` for row 13.
