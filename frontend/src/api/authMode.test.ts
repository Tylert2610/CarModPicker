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
    expect(resolveAuthMode({ [AUTH_MODE_ENV_KEY]: ' identity ' })).toBe(
      'identity'
    );
  });

  it('rejects an unrecognised value rather than guessing', () => {
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
    expect(
      resolveAuthMode({ [AUTH_MODE_ENV_KEY]: IDENTITY_CUTOVER.enabledValue })
    ).toBe('identity');
  });
});
