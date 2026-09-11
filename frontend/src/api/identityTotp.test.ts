import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type Stub = Record<string, ReturnType<typeof vi.fn>>;

const loadWith = async (stub: Stub | null) => {
  vi.resetModules();
  vi.doMock('./identityClient', () => ({
    getIdentityClient: () => stub,
  }));
  return import('./identityTotp');
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.doUnmock('./identityClient');
  vi.resetModules();
});

describe('enrolTotp', () => {
  it('returns the secret and the provisioning URI', async () => {
    const enrol = vi.fn().mockResolvedValue({
      ok: true,
      secret: 'ABCDEF',
      provisioningUri: 'otpauth://totp/CarModPicker:me?secret=ABCDEF',
    });
    const { enrolTotp } = await loadWith({ enrolTotp: enrol });
    await expect(enrolTotp()).resolves.toEqual({
      status: 'ok',
      value: {
        secret: 'ABCDEF',
        provisioningUri: 'otpauth://totp/CarModPicker:me?secret=ABCDEF',
      },
    });
  });

  it("renders the server's sentence for a refusal", async () => {
    const enrol = vi.fn().mockResolvedValue({
      ok: false,
      reason: 'already-enabled',
      message: 'Two factor authentication is already on.',
    });
    const { enrolTotp } = await loadWith({ enrolTotp: enrol });
    await expect(enrolTotp()).resolves.toEqual({
      status: 'failed',
      error: 'Two factor authentication is already on.',
    });
  });
});

describe('activateTotp', () => {
  it('sends only the code, never a password', async () => {
    const activate = vi
      .fn()
      .mockResolvedValue({ ok: true, recoveryCodes: ['a', 'b'] });
    const { activateTotp } = await loadWith({ activateTotp: activate });
    await activateTotp(' 123456 ');
    expect(activate).toHaveBeenCalledWith({ code: '123456' });
  });

  it('returns the recovery codes, which are shown exactly once', async () => {
    const codes = Array.from({ length: 10 }, (_, i) => `code-${i}`);
    const activate = vi
      .fn()
      .mockResolvedValue({ ok: true, recoveryCodes: codes });
    const { activateTotp } = await loadWith({ activateTotp: activate });
    await expect(activateTotp('123456')).resolves.toEqual({
      status: 'ok',
      value: codes,
    });
  });
});

describe('disableTotp', () => {
  it('sends only the code', async () => {
    const disable = vi.fn().mockResolvedValue({ ok: true });
    const { disableTotp } = await loadWith({ disableTotp: disable });
    await expect(disableTotp('123456')).resolves.toEqual({
      status: 'ok',
      value: null,
    });
    expect(disable).toHaveBeenCalledWith({ code: '123456' });
  });
});

describe('regenerateRecoveryCodes', () => {
  it('returns a replacement set', async () => {
    const regenerate = vi
      .fn()
      .mockResolvedValue({ ok: true, recoveryCodes: ['new-1'] });
    const { regenerateRecoveryCodes } = await loadWith({
      regenerateRecoveryCodes: regenerate,
    });
    await expect(regenerateRecoveryCodes('123456')).resolves.toEqual({
      status: 'ok',
      value: ['new-1'],
    });
  });
});

describe('in bearer mode', () => {
  it('refuses every operation rather than throwing', async () => {
    const module = await loadWith(null);
    for (const result of await Promise.all([
      module.enrolTotp(),
      module.activateTotp('123456'),
      module.disableTotp('123456'),
      module.regenerateRecoveryCodes('123456'),
    ])) {
      expect(result.status).toBe('failed');
    }
  });
});
