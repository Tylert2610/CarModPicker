// The mode switch. These are the tests that stand between a mistyped
// environment variable and a production bundle that talks to the wrong auth
// service, so they cover the fall-through cases as carefully as the happy one.
import { describe, expect, it } from 'vitest';
import {
  AUTH_MODES,
  AUTH_MODE_ENV_KEY,
  identityAvailability,
  resolveAuthMode,
  IDENTITY_CUTOVER,
} from './authMode';

describe('resolveAuthMode', () => {
  it('defaults to bearer when the variable is absent', () => {
    expect(resolveAuthMode({})).toBe('bearer');
  });

  it('defaults to bearer when the variable is an empty string', () => {
    // This is the case that actually happens. GitHub Actions expands
    // `${{ vars.AUTH_MODE }}` to an empty string when the repository variable
    // is not set, so every build until the cutover takes this branch. Treating
    // it as an unrecognised value would fail every deploy.
    expect(resolveAuthMode({ [AUTH_MODE_ENV_KEY]: '' })).toBe('bearer');
  });

  it('defaults to bearer when the variable is only whitespace', () => {
    expect(resolveAuthMode({ [AUTH_MODE_ENV_KEY]: '   ' })).toBe('bearer');
  });

  it('defaults to bearer when the variable is not a string', () => {
    expect(resolveAuthMode({ [AUTH_MODE_ENV_KEY]: 1 })).toBe('bearer');
  });

  it('reads bearer', () => {
    expect(resolveAuthMode({ [AUTH_MODE_ENV_KEY]: 'bearer' })).toBe('bearer');
  });

  it('reads identity', () => {
    expect(resolveAuthMode({ [AUTH_MODE_ENV_KEY]: 'identity' })).toBe(
      'identity'
    );
  });

  it('trims surrounding whitespace', () => {
    // A value pasted into the GitHub UI with a trailing space should not
    // silently select the legacy flow.
    expect(resolveAuthMode({ [AUTH_MODE_ENV_KEY]: ' identity ' })).toBe(
      'identity'
    );
  });

  it('rejects an unrecognised value rather than guessing', () => {
    // `assertValid` throws, which is the point: a typo becomes a named startup
    // failure rather than a bundle that quietly runs the other mechanism.
    expect(() => resolveAuthMode({ [AUTH_MODE_ENV_KEY]: 'oauth' })).toThrow();
  });

  it('ignores unrelated keys', () => {
    expect(resolveAuthMode({ VITE_API_URL: 'https://example.test' })).toBe(
      'bearer'
    );
  });

  it('exposes exactly the two modes', () => {
    expect([...AUTH_MODES]).toEqual(['bearer', 'identity']);
  });
});

describe('identityAvailability', () => {
  it('offers passkeys and Google in bearer mode', () => {
    const available = identityAvailability('bearer');
    expect(available.passkeys).toBe(true);
    expect(available.googleOauth).toBe(true);
  });

  it('offers passkeys and OAuth in identity mode too', () => {
    // Both shipped: `@webbpulse/auth` 0.8.0 carries the passkey ceremonies and
    // the OAuth link surface, and webbpulse-python 0.16.0 serves the routes.
    // An earlier revision asserted false here, back when the server side
    // package had only M1 to M4.
    //
    // Whether a *deployment* has either switched on is a different question,
    // asked at runtime by `./passkeyAvailability` and `./oauthProviders`.
    const available = identityAvailability('identity');
    expect(available.passkeys).toBe(true);
    expect(available.googleOauth).toBe(true);
  });

  it('offers password and TOTP in both modes', () => {
    for (const mode of AUTH_MODES) {
      const available = identityAvailability(mode);
      expect(available.password).toBe(true);
      expect(available.totp).toBe(true);
    }
  });

  it('offers recovery codes only in identity mode', () => {
    // The legacy TOTP flow issues none, which is why a cutover has to prompt
    // every already-enrolled user to generate a set.
    expect(identityAvailability('bearer').recoveryCodes).toBe(false);
    expect(identityAvailability('identity').recoveryCodes).toBe(true);
  });
});

describe('IDENTITY_CUTOVER', () => {
  it('names the Environment variable and the value that turns identity on', () => {
    expect(IDENTITY_CUTOVER.environmentVariable).toBe('AUTH_MODE');
    expect(IDENTITY_CUTOVER.enabledValue).toBe('identity');
  });

  it('names a value the resolver actually accepts', () => {
    // The two constants are documentation until something ties them together.
    expect(
      resolveAuthMode({ [AUTH_MODE_ENV_KEY]: IDENTITY_CUTOVER.enabledValue })
    ).toBe('identity');
  });
});
