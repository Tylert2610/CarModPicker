# TOTP seed encryption

Status: finding recorded, not yet fixed. Found during the identity standard
design. The work belongs to the identity milestone, not to the pull request that
created this file.

## The finding

TOTP shared secrets are stored in DynamoDB as plaintext base32.

`app/db/dynamo/users.py` declares the field on the user item:

```python
totp_secret: str | None = None
```

`app/api/endpoints/auth/two_factor.py` writes it straight from
`pyotp.random_base32()`:

```python
secret = pyotp.random_base32()
repos.users.update(current_user.id, totp_secret=secret)
```

and every verification path reads it back and hands it to `pyotp.TOTP(...)`
unchanged: `auth/two_factor.py` (setup verify, disable), `auth/core.py` (the
password login second factor) and `auth/oauth.py` (the Google login second
factor).

So the value that sits in the `users` table is the enrolled authenticator's
seed. Anyone who can read the item can generate that user's codes indefinitely,
which is the whole of the second factor. It is materially unlike the password on
the same item: `hashed_password` is a one-way hash, so a table read does not
yield a usable credential, while `totp_secret` is symmetric and a table read
does.

Two further consequences worth naming:

- The seed is written at *setup* time, before the user has proved possession by
  entering a code, so an abandoned enrolment leaves a live plaintext seed on the
  item.
- It is in scope for any backup or export of the table. Production has
  point in time recovery on (`terraform/dynamodb.tf`), so restores and any
  future export inherit the plaintext.

## What protects it today

- DynamoDB encryption at rest, with the AWS owned key. The tables do not set
  `server_side_encryption`, so they take the module default. This defends the
  disk, not a read: anything holding `dynamodb:GetItem` on the table sees
  plaintext, and there is no second authorization step and no separate audit
  trail on the seed.
- IAM scoping of the table to the identity Lambda's execution role.
- No application log emits the field. That was checked; keep it that way.

Encryption at rest is doing real work here, but it is the wrong control for this
value. It cannot distinguish "the identity function reading a seed to verify a
login" from "an over-broad role scanning the users table".

## Intended design: KMS envelope encryption with per-user encryption context

Encrypt the seed under a customer managed KMS key before it is written, and
decrypt only on the verification path.

- **Key.** One customer managed key per environment,
  `alias/carmodpicker-<env>-totp-seeds`, declared in Terraform alongside the
  tables. Its key policy grants `kms:Decrypt` only to the identity function's
  execution role and `kms:Encrypt` only to the enrolment path's role. Nothing
  else in the account gets either, including administrators, so a broad
  `dynamodb:Scan` no longer yields credentials.
- **Encryption context.** Bind every operation to the user it belongs to:

  ```
  {"user_id": "<uuid>", "purpose": "totp_seed"}
  ```

  The context is authenticated but not secret, and KMS refuses a decrypt whose
  context does not match the encrypt. That is what stops a seed lifted from one
  user's item from being decrypted in the course of authenticating another, and
  it puts `user_id` into every CloudTrail `Decrypt` event, so "which seeds did
  this role decrypt, and when" becomes an answerable question.
- **Envelope, not direct encrypt.** Seeds are ~32 bytes and would fit a direct
  `kms:Encrypt`, but envelope encryption is still the right shape: it keeps the
  per-item ciphertext self describing, and it leaves room for the same helper to
  wrap the recovery codes, which are longer and are the next thing that needs
  this. Use `GenerateDataKey`, encrypt with AES-256-GCM, discard the plaintext
  data key, and store the wrapped key with the ciphertext. Cache data keys per
  execution environment with a short lifetime so a login burst does not become a
  KMS call per request.
- **Stored shape.** A new field rather than an overloaded one, so the type says
  what the value is and a plaintext seed cannot be mistaken for a ciphertext:

  ```python
  totp_secret_encrypted: str | None = None  # versioned envelope, base64
  ```

  Prefix the payload with a scheme version (`v1:`) so the format can change
  without a second migration.
- **Blast radius.** Decryption stays behind one module. No endpoint calls KMS
  directly, and the plaintext seed never leaves the function that verifies the
  code, is never logged, and is never returned in a response.

## Migration

The constraint is that the seed cannot be re-derived. A user whose seed is lost
must re-enrol their authenticator, so the migration has to be lazy and
reversible rather than a one-shot rewrite.

1. **Add the field and the helper.** Ship `totp_secret_encrypted` and the
   encrypt/decrypt module with the key in place, reading nothing yet. No
   behaviour change.
2. **Write new, read either.** Enrolment writes only the encrypted field.
   Verification prefers `totp_secret_encrypted` and falls back to
   `totp_secret`. Every existing user keeps working, and no user is asked to
   re-enrol.
3. **Migrate on use, then sweep.** On a successful verification that came from
   the plaintext fallback, re-write the item with the encrypted field and clear
   the plaintext one, so active users convert themselves. Follow with a
   backfill job over the remainder, which reads and rewrites without ever
   logging a seed.
4. **Fail closed and remove.** Once a metric on the fallback path reads zero,
   drop the fallback, drop `totp_secret` from the model, and let a decrypt
   failure be an authentication failure rather than a bypass. A user whose seed
   cannot be decrypted re-enrols through the existing setup flow.
5. **Backups.** Plaintext seeds persist in point in time recovery for its
   retention window after step 4. Note the date the window closes; until then a
   restore has to be treated as carrying live seeds.

Steps 2 and 3 are separately deployable, and each of 1 through 3 is safe to roll
back. Step 4 is the only one that is not, and it should wait for the metric.

## Related

Recovery codes deserve the same treatment and are not covered here. Whatever
lands for seeds should be built so the same helper wraps them.
