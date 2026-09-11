// What is left of the mode switch after row 13.
//
// These used to be the tests standing between a mistyped environment variable
// and a production bundle pointed at the wrong auth service. Row 13 deleted the
// 24 routes under `/api/auth` that the other mode talked to, so there is no
// wrong service left to point at and `AUTH_MODE` is a constant.
//
// They are kept rather than deleted because the constant is load bearing: a
// later change that reintroduces a second mode, or that quietly turns an
// affordance off, should have to edit a test that says so out loud.
import { describe, expect, it } from 'vitest';
import { AUTH_MODE, AUTH_MODES, identityAvailability } from './authMode';

describe('AUTH_MODE', () => {
  it('is identity, and is the only mode', () => {
    expect(AUTH_MODE).toBe('identity');
    expect([...AUTH_MODES]).toEqual(['identity']);
  });

  it('reads nothing from the environment', () => {
    // The point of the constant. A leftover `VITE_AUTH_MODE=bearer` in some
    // environment must not be able to build a bundle that talks to routes
    // which no longer exist, which would be a blank page rather than a
    // fallback.
    expect(AUTH_MODE).toBe('identity');
    expect(import.meta.env['VITE_AUTH_MODE']).toBeUndefined();
  });
});

describe('identityAvailability', () => {
  it('takes no argument', () => {
    expect(identityAvailability).toHaveLength(0);
  });

  it('offers password and TOTP', () => {
    const available = identityAvailability();
    expect(available.password).toBe(true);
    expect(available.totp).toBe(true);
  });

  it('offers passkeys and Google', () => {
    // Both shipped: `@webbpulse/auth` carries the passkey ceremonies and the
    // OAuth link surface, and the identity service serves the routes.
    //
    // Whether a *deployment* has either switched on is a different question,
    // asked at runtime by `./passkeyAvailability` and `./oauthProviders`.
    const available = identityAvailability();
    expect(available.passkeys).toBe(true);
    expect(available.googleOauth).toBe(true);
  });

  it('offers recovery codes', () => {
    // Only the identity service issues these. The legacy TOTP flow had none,
    // which is why the cutover prompted every enrolled user to generate a set.
    expect(identityAvailability().recoveryCodes).toBe(true);
  });
});
