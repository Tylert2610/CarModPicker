/**
 * Which auth mechanism this bundle runs. There is only one left.
 *
 * Two mechanisms used to exist in the estate and CarModPicker was between them.
 * `bearer` signed in against `POST /api/auth/token`, kept an HS256 token in
 * `localStorage` through `./tokenStore`, and carried it on every request.
 * `identity` is the unified identity standard, which `@webbpulse/auth`
 * implements as `AuthClient`: a short lived access token held in memory only, an
 * httpOnly refresh cookie the page cannot read, one shared in-flight refresh,
 * and a retry-once-on-401 pipeline.
 *
 * Row 12 of `docs/identity-adoption.md` flipped every environment to
 * `identity`. Row 13 deleted the 24 routes under `/api/auth` that the bearer
 * path talked to, so there is no longer a server on the other end of it: this
 * module keeps its name and its shape, and `AUTH_MODE` is now a constant.
 *
 * **Why this file still exists rather than being deleted outright.** Two
 * reasons, and neither is sentiment.
 *
 * `identityAvailability` is a real function with real callers that ask which
 * sign in affordances to render, and it needs somewhere to live. Folding it into
 * each call site would scatter the answer.
 *
 * And a constant is what makes the deletion checkable. Every remaining
 * `AUTH_MODE === 'identity'` test is now provably true, so a type checker and a
 * reader can both see that the branch below it is the only one, rather than
 * inferring it from the absence of a variable. The follow up that removes those
 * tests is an ordinary simplification with no behaviour in it.
 *
 * **`VITE_AUTH_MODE` is gone**, along with the `AUTH_MODE` GitHub Environment
 * variable it was built from. See `docs/identity-migration-runbook.md` for the
 * owner checklist that deletes it.
 */

/** The one mechanism. */
export const AUTH_MODES = ['identity'] as const;

/** One of {@link AUTH_MODES}. */
export type AuthMode = (typeof AUTH_MODES)[number];

/**
 * The mode this bundle holds for its lifetime.
 *
 * A constant rather than a read of `import.meta.env`. Nothing selects it any
 * more, and leaving the environment lookup in place would mean an environment
 * that still sets `VITE_AUTH_MODE=bearer` would build a bundle pointed at 24
 * routes that no longer exist, which is a blank page rather than a fallback.
 */
export const AUTH_MODE: AuthMode = 'identity';

/**
 * Which sign in affordances this bundle can serve at all.
 *
 * One place rather than a test at each call site.
 *
 * **This says "the bundle has this", not "this deployment has this."** Whether a
 * given backend actually has passwordless passkey sign in switched on, or any
 * OAuth provider configured, is a runtime question a build time constant cannot
 * answer. `./passkeyAvailability` and `./oauthProviders` ask it, and the
 * components hide themselves on the answer rather than rendering a disabled
 * control, because a control that cannot work in this deployment is not a
 * temporary state the user can wait out.
 */
export const identityAvailability = (): {
  password: boolean;
  totp: boolean;
  passkeys: boolean;
  googleOauth: boolean;
  recoveryCodes: boolean;
} => ({
  password: true,
  totp: true,
  passkeys: true,
  googleOauth: true,
  // Only the identity service issues recovery codes. The legacy TOTP flow had
  // none, which is why the cutover prompted every enrolled user to generate a
  // set.
  recoveryCodes: true,
});
