/**
 * Which auth mechanism this bundle runs.
 *
 * Two mechanisms exist in the estate and CarModPicker is between them.
 *
 * `bearer` is what ships today and what every environment still runs.
 * `POST /api/auth/token` answers with an HS256 bearer token in the body, the
 * token goes into `localStorage` through `./tokenStore`, and every request
 * carries it through the shared client's `getAuthToken`. There is no refresh
 * route and no refresh cookie, so the token lives until it expires and the
 * user signs in again. Passkeys, Google sign in and TOTP all hang off that
 * same mechanism.
 *
 * `identity` is the unified identity standard, which `@webbpulse/auth` 0.8.0
 * implements as `AuthClient`: a short lived access token held in memory only,
 * an httpOnly refresh cookie the page cannot read, one shared in-flight
 * refresh, and a retry-once-on-401 pipeline turned on by handing the client to
 * `createApiClient` as `auth`.
 *
 * The switch is configuration rather than a branch waiting on a rewrite. The
 * `identity` path is written and typed against the real 0.8.0 API, so turning
 * it on is a deploy time decision and not a code change.
 *
 * **Passkeys and OAuth are in the identity path as of 0.8.0.** An earlier
 * revision of this file hid both, because the server side package had shipped
 * M1 to M4 only and its own router said "Passkeys and OAuth are M5 and M6".
 * Both milestones have since landed: `@webbpulse/auth` 0.8.0 carries the
 * passkey ceremonies and the OAuth link surface, and webbpulse-python 0.16.0
 * serves `/api/auth/passkeys/*`, `/api/auth/login/passkey/*` and the OAuth
 * routes including a `GET /api/auth/oauth/providers` discovery route.
 * webbpulse-python 0.17.0 adds the matching one for passkeys,
 * `GET /api/auth/passkeys/availability`.
 *
 * So neither capability is gated on the mode any more. What they are gated on
 * is the *deployment*, which is a different question and not one a constant can
 * answer: a backend can have passkey enrolment mounted with passwordless sign
 * in switched off, and can have no OAuth provider configured at all. Those are
 * asked at runtime by `./passkeyAvailability` and `./oauthProviders` rather
 * than assumed here.
 *
 * Read through `@webbpulse/config`'s `ConfigReader` rather than
 * `import.meta.env` directly, so an unrecognised value is a named startup
 * failure alongside every other configuration problem instead of a silent
 * fall through to the default.
 */
import { ConfigReader } from '@webbpulse/config';

/** The two mechanisms. */
export const AUTH_MODES = ['bearer', 'identity'] as const;

/** One of {@link AUTH_MODES}. */
export type AuthMode = (typeof AUTH_MODES)[number];

/**
 * The env var that selects the mechanism. Absent or empty means `bearer`.
 *
 * Named for what it selects rather than for a flag, because it outlives the
 * migration only as the value `identity` and then goes away entirely with the
 * bearer branch.
 */
export const AUTH_MODE_ENV_KEY = 'VITE_AUTH_MODE';

/**
 * Resolves the mode from an environment bag.
 *
 * Exported separately from the singleton below so a test can drive it with a
 * synthetic bag rather than the real `import.meta.env`.
 *
 * An empty string is treated as unset, because that is what a GitHub Actions
 * `${{ vars.AUTH_MODE }}` expands to when the repository variable is not set,
 * and the build must fall through to `bearer` rather than fail.
 */
export const resolveAuthMode = (env: Record<string, unknown>): AuthMode => {
  const raw = env[AUTH_MODE_ENV_KEY];
  if (typeof raw !== 'string' || raw.trim() === '') return 'bearer';
  const reader = new ConfigReader({ ...env, [AUTH_MODE_ENV_KEY]: raw.trim() });
  const mode = reader.oneOf(AUTH_MODE_ENV_KEY, AUTH_MODES, 'bearer');
  reader.assertValid();
  return mode;
};

/** The mode this bundle holds for its lifetime, read once at startup. */
export const AUTH_MODE: AuthMode = resolveAuthMode(import.meta.env);

/**
 * Which sign in affordances the current mode can serve at all.
 *
 * One place rather than an `AUTH_MODE === 'identity'` test at each call site.
 *
 * Every affordance except `recoveryCodes` is now true in both modes, because
 * both mechanisms carry all of them: the wire protocols differ and the user
 * facing affordance does not. `recoveryCodes` is the one real asymmetry, since
 * only the identity service issues them and the legacy TOTP flow has none,
 * which is why a cutover prompts every enrolled user to generate a set.
 *
 * **This says "the mode has this", not "this deployment has this."** Whether a
 * given backend actually has passwordless passkey sign in switched on, or any
 * OAuth provider configured, is a runtime question that a build time constant
 * cannot answer. `./passkeyAvailability` and `./oauthProviders` ask it, and the
 * components hide themselves on the answer rather than rendering a disabled
 * control, because a control that cannot work in this deployment is not a
 * temporary state the user can wait out.
 *
 * In bearer mode the two flags stay true and the legacy implementations behind
 * them are exactly as they were: `@simplewebauthn/browser` against
 * `/auth/webauthn/*`, and `@react-oauth/google`. Nothing about `main` changes.
 */
export const identityAvailability = (
  mode: AuthMode = AUTH_MODE
): {
  password: boolean;
  totp: boolean;
  passkeys: boolean;
  googleOauth: boolean;
  recoveryCodes: boolean;
} => ({
  password: true,
  totp: true,
  // Shipped in both mechanisms as of `@webbpulse/auth` 0.8.0 and
  // webbpulse-python 0.16.0. See the module note.
  passkeys: true,
  googleOauth: true,
  // Only the identity service issues recovery codes; the legacy TOTP flow has
  // none, which is why a cutover prompts every enrolled user to generate a set.
  recoveryCodes: mode === 'identity',
});

/**
 * How the cutover is performed, in one place.
 *
 * A deployment decision rather than a code change: setting the `AUTH_MODE`
 * variable on a GitHub Environment to `identity` and redeploying switches that
 * environment over, and clearing it back to empty rolls the whole thing back
 * with another redeploy. Nothing about the bundle's source differs between the
 * two, which is what makes the rollback a redeploy rather than a revert.
 */
export const IDENTITY_CUTOVER = {
  /** The GitHub Environment variable that selects the mode at build time. */
  environmentVariable: 'AUTH_MODE',
  /** The value that turns the identity mode on. */
  enabledValue: 'identity',
} as const;
