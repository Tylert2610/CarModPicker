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
 * `identity` is the unified identity standard, which `@webbpulse/auth` 0.6.0
 * implements as `AuthClient`: a short lived access token held in memory only,
 * an httpOnly refresh cookie the page cannot read, one shared in-flight
 * refresh, and a retry-once-on-401 pipeline turned on by handing the client to
 * `createApiClient` as `auth`.
 *
 * The switch is configuration rather than a branch waiting on a rewrite. The
 * `identity` path is written and typed against the real 0.6.0 API, so turning
 * it on is a deploy time decision and not a code change. What it is waiting on
 * is rows 4, 5 and 8 of the adoption plan: the Terraform module, the backend
 * hooks that mount M1 to M4 under `/api/auth`, and the migration of the
 * existing password hashes and TOTP seeds. Until those land, setting this to
 * `identity` would point the bundle at routes the backend does not serve.
 *
 * **Passkeys and Google sign in are not in the identity path.** The server
 * side package has shipped M1 through M4 only, and its own router says
 * plainly that "Passkeys and OAuth are M5 and M6". `AuthClient` carries client
 * side methods for both, but there is nothing behind them until those
 * milestones ship, so identity mode hides that UI rather than rendering
 * buttons that 404. See `identityAvailability` below.
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
 * Which sign in affordances the current mode can actually serve.
 *
 * One place rather than an `AUTH_MODE === 'identity'` test at each of the six
 * call sites, so the day M5 and M6 land is one edit here rather than a hunt
 * through the login page, the profile dialogs and their tests.
 *
 * `password` and `totp` are true in both modes: the mechanisms differ, but the
 * user facing affordance exists either way. `passkeys` and `googleOauth` are
 * true only in bearer mode, and the components read them to hide themselves
 * rather than to render a disabled control, because a control that cannot work
 * in this deployment is not a temporary state the user can wait out.
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
  // M5 and M6 in the server side package. See the module note.
  passkeys: mode === 'bearer',
  googleOauth: mode === 'bearer',
  // Only the identity service issues recovery codes; the legacy TOTP flow has
  // none, which is why a cutover prompts every enrolled user to generate a set.
  recoveryCodes: mode === 'identity',
});

/**
 * What the cutover still needs, in one place.
 *
 * A deployment decision rather than code once rows 4, 5 and 8 land: setting
 * `AUTH_MODE=identity` on a GitHub Environment switches that environment over,
 * and setting it back to empty rolls the whole thing back with a redeploy.
 */
export const IDENTITY_CUTOVER = {
  /** The GitHub Environment variable that selects the mode at build time. */
  environmentVariable: 'AUTH_MODE',
  /** The value that turns the identity mode on. */
  enabledValue: 'identity',
} as const;
