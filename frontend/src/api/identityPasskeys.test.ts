import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type Stub = Record<string, ReturnType<typeof vi.fn>>;

/** Loads the module with `getIdentityClient` returning `stub`, or null. */
const loadWith = async (stub: Stub | null) => {
  vi.resetModules();
  vi.doMock('./identityClient', () => ({
    getIdentityClient: () => stub,
    identityUrl: (path: string) => `https://api.test${path}`,
  }));
  return import('./identityPasskeys');
};

const passkey = {
  credentialId: 'cred-1',
  name: 'Laptop',
  createdAt: '2026-01-01T00:00:00Z',
  lastUsedAt: undefined,
  transports: ['internal'],
  aaguid: '',
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.doUnmock('./identityClient');
  vi.resetModules();
});

describe('enrolPasskey', () => {
  it('returns the enrolled credential', async () => {
    const registerPasskey = vi.fn().mockResolvedValue({ ok: true, passkey });
    const { enrolPasskey } = await loadWith({ registerPasskey });
    await expect(enrolPasskey('Laptop')).resolves.toEqual({
      status: 'ok',
      value: passkey,
    });
    expect(registerPasskey).toHaveBeenCalledWith({ name: 'Laptop' });
  });

  it('sends no name when none was given, letting the server default it', async () => {
    const registerPasskey = vi.fn().mockResolvedValue({ ok: true, passkey });
    const { enrolPasskey } = await loadWith({ registerPasskey });
    await enrolPasskey('   ');
    expect(registerPasskey).toHaveBeenCalledWith({});
  });

  it('reports a dismissed sheet as cancelled, not as a failure', async () => {
    const registerPasskey = vi
      .fn()
      .mockResolvedValue({ ok: false, reason: 'cancelled', message: 'x' });
    const { enrolPasskey } = await loadWith({ registerPasskey });
    await expect(enrolPasskey('Laptop')).resolves.toEqual({
      status: 'cancelled',
    });
  });

  it("renders the server's own sentence for a refusal", async () => {
    const registerPasskey = vi.fn().mockResolvedValue({
      ok: false,
      reason: 'rate-limited',
      message: 'Too many attempts. Wait a few minutes.',
    });
    const { enrolPasskey } = await loadWith({ registerPasskey });
    await expect(enrolPasskey('Laptop')).resolves.toEqual({
      status: 'failed',
      error: 'Too many attempts. Wait a few minutes.',
    });
  });

  it('refuses when this bundle runs the legacy mechanism', async () => {
    const { enrolPasskey } = await loadWith(null);
    const result = await enrolPasskey('Laptop');
    expect(result.status).toBe('failed');
  });
});

describe('listPasskeys', () => {
  it('returns the credentials', async () => {
    const listPasskeys = vi
      .fn()
      .mockResolvedValue({ ok: true, passkeys: [passkey] });
    const module = await loadWith({ listPasskeys });
    await expect(module.listPasskeys()).resolves.toEqual({
      status: 'ok',
      value: [passkey],
    });
  });
});

describe('renamePasskey', () => {
  it('sends the credential id and the new name', async () => {
    const renamePasskey = vi.fn().mockResolvedValue({ ok: true, passkey });
    const module = await loadWith({ renamePasskey });
    await module.renamePasskey('cred-1', 'Desktop');
    expect(renamePasskey).toHaveBeenCalledWith('cred-1', 'Desktop');
  });
});

describe('deletePasskey', () => {
  it('removes the credential', async () => {
    const deletePasskey = vi.fn().mockResolvedValue({ ok: true });
    const module = await loadWith({ deletePasskey });
    await expect(module.deletePasskey('cred-1')).resolves.toEqual({
      status: 'ok',
      value: null,
    });
  });

  it("keeps the last credential rule's own sentence", async () => {
    const deletePasskey = vi.fn().mockResolvedValue({
      ok: false,
      reason: 'last-credential',
      message:
        'This is the only way into your account. Set a password or add another passkey first.',
    });
    const module = await loadWith({ deletePasskey });
    await expect(module.deletePasskey('cred-1')).resolves.toEqual({
      status: 'failed',
      error:
        'This is the only way into your account. Set a password or add another passkey first.',
    });
  });
});

describe('signInWithPasskey', () => {
  it('reports a completed sign in', async () => {
    const signIn = vi.fn().mockResolvedValue({ ok: true, kind: 'signed-in' });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await expect(signInWithPasskey()).resolves.toEqual({
      status: 'authenticated',
    });
  });

  it('carries an MFA ticket through to the second leg', async () => {
    const signIn = vi.fn().mockResolvedValue({
      ok: true,
      kind: 'mfa-required',
      ticket: 'tick-1',
      factors: ['totp'],
    });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await expect(signInWithPasskey()).resolves.toEqual({
      status: 'mfa-required',
      ticket: 'tick-1',
      factors: ['totp'],
    });
  });

  it('passes the mediation through so the page can ask for conditional', async () => {
    const signIn = vi.fn().mockResolvedValue({ ok: true, kind: 'signed-in' });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await signInWithPasskey({ mediation: 'conditional' });
    expect(signIn).toHaveBeenCalledWith({ mediation: 'conditional' });
  });

  it('sends a username as an email when one was typed', async () => {
    const signIn = vi.fn().mockResolvedValue({ ok: true, kind: 'signed-in' });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await signInWithPasskey({ username: '  me@example.com  ' });
    expect(signIn).toHaveBeenCalledWith({ email: 'me@example.com' });
  });

  it('reports a cancellation as cancelled', async () => {
    const signIn = vi
      .fn()
      .mockResolvedValue({ ok: false, reason: 'cancelled', message: 'x' });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await expect(signInWithPasskey()).resolves.toEqual({
      status: 'cancelled',
    });
  });

  it('reports a refusal with the server sentence', async () => {
    const signIn = vi.fn().mockResolvedValue({
      ok: false,
      reason: 'unknown-credential',
      message: 'That passkey is not registered.',
    });
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await expect(signInWithPasskey()).resolves.toEqual({
      status: 'failed',
      error: 'That passkey is not registered.',
    });
  });

  it('reports a thrown error as a failure', async () => {
    const signIn = vi.fn().mockRejectedValue(new Error('network down'));
    const { signInWithPasskey } = await loadWith({
      signInWithPasskey: signIn,
    });
    await expect(signInWithPasskey()).resolves.toEqual({
      status: 'failed',
      error: 'network down',
    });
  });
});
