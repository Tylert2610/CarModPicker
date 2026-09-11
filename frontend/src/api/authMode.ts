/**
 * Selects the auth mechanism this bundle runs: `bearer`, a stored token with no
 * refresh route, or `identity`, an in-memory access token behind an httpOnly
 * refresh cookie. Configuration only, so a cutover is a redeploy.
 */
import { ConfigReader } from '@webbpulse/config';

/** The two mechanisms. */
export const AUTH_MODES = ['bearer', 'identity'] as const;

/** One of {@link AUTH_MODES}. */
export type AuthMode = (typeof AUTH_MODES)[number];

/** The env var that selects the mechanism. Absent or empty means `bearer`. */
export const AUTH_MODE_ENV_KEY = 'VITE_AUTH_MODE';

/**
 * Resolves the mode from an environment bag, treating an empty string as unset
 * so an unset CI variable falls through to `bearer` rather than failing the
 * build. Exported separately so tests can pass a synthetic bag.
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
 * Which sign in affordances the mode itself can serve; only `recoveryCodes`
 * differs, as the legacy TOTP flow issues none. Whether a given deployment has
 * one switched on is a runtime question for the availability modules.
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
  passkeys: true,
  googleOauth: true,
  recoveryCodes: mode === 'identity',
});

/**
 * Names the GitHub Environment variable and value that perform the cutover, so
 * switching over and rolling back are both a redeploy rather than a revert.
 */
export const IDENTITY_CUTOVER = {
  /** The GitHub Environment variable that selects the mode at build time. */
  environmentVariable: 'AUTH_MODE',
  /** The value that turns the identity mode on. */
  enabledValue: 'identity',
} as const;
