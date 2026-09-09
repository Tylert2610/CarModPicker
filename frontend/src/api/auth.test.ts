// Phase 8 plan 08-02: authApi coverage tests.
//
// Covers every exported method on `authApi` (23 total) plus the branching
// behavior inside `login`, `loginWith2FA`, `webauthnLoginVerify`, `googleLink`,
// `googleSignup`, and `oauthTwoFactor` (token-storage side effects + user-
// payload unwrap semantics). Also covers the special `logout` path that calls
// `removeStoredToken` after a successful POST.
//
// Mocking pattern (canonical Wave 1 — see PATTERNS.md §7): setup.ts (Phase 8
// D-18) installs `vi.mock('../api/client')` globally, which means importing
// `apiClient`, `setStoredToken`, and `removeStoredToken` from `./client` gives
// us `vi.fn()` references automatically. We narrow each mock at module scope
// via a cast to `MockedFunction<typeof apiClient.<verb>>` / `typeof
// setStoredToken`, which lets us use the mock methods (`mockResolvedValueOnce`,
// `toHaveBeenCalledWith`) without the per-call lint noise.
//
// Lint note: `@typescript-eslint/unbound-method` fires on `apiClient.<verb>` in
// argument position (detached method reference). Since apiClient IS the mock,
// the cast is runtime-safe — we silence the rule at each module-scope capture.
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockedFunction,
} from 'vitest';
import { apiClient, setStoredToken, removeStoredToken } from './client';
import { authApi } from './auth';
import { mockUser } from '../test/mocks/api';

const postMock = apiClient.post as MockedFunction<typeof apiClient.post>;

const getMock = apiClient.get as MockedFunction<typeof apiClient.get>;

const patchMock = apiClient.patch as MockedFunction<typeof apiClient.patch>;

const deleteMock = apiClient.delete as MockedFunction<typeof apiClient.delete>;
const setStoredTokenMock = setStoredToken as MockedFunction<
  typeof setStoredToken
>;
const removeStoredTokenMock = removeStoredToken as MockedFunction<
  typeof removeStoredToken
>;

describe('authApi — login', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('login POSTs form-urlencoded body to /auth/token and stores the access_token', async () => {
    const data = {
      username: 'testuser',
      password: 'pw',
      grant_type: 'password' as const,
    };
    postMock.mockResolvedValueOnce({
      data: {
        access_token: 'tok-123',
        token_type: 'bearer',
        user: mockUser,
        requires_2fa: false,
      },
    });

    const result = await authApi.login(data);

    expect(postMock).toHaveBeenCalledWith('/auth/token', data, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    expect(setStoredTokenMock).toHaveBeenCalledWith('tok-123');
    expect(result.data).toEqual(mockUser);
  });

  it('login returns response as-is when requires_2fa is truthy (no setStoredToken)', async () => {
    const data = {
      username: 'testuser',
      password: 'pw',
      grant_type: 'password' as const,
    };
    postMock.mockResolvedValueOnce({
      data: {
        requires_2fa: true,
        session_token: 'session-abc',
      },
    });

    const result = await authApi.login(data);

    expect(postMock).toHaveBeenCalledWith('/auth/token', data, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    expect(setStoredTokenMock).not.toHaveBeenCalled();
    expect((result.data as { requires_2fa?: boolean }).requires_2fa).toBe(true);
  });

  it('login throws when the response is missing a user payload (contract violation)', async () => {
    postMock.mockResolvedValueOnce({
      data: {
        access_token: 'tok-456',
        token_type: 'bearer',
        // intentionally no user field
      },
    });

    await expect(
      authApi.login({
        username: 'x',
        password: 'y',
        grant_type: 'password' as const,
      })
    ).rejects.toThrow(/missing user payload/);
  });
});

describe('authApi — TOTP 2FA', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loginWith2FA POSTs /auth/token/2fa, stores token, and unwraps user', async () => {
    const data = { username: 'u', password: 'p', otp: '123456' };
    postMock.mockResolvedValueOnce({
      data: {
        access_token: 'tfa-tok',
        token_type: 'bearer',
        user: mockUser,
      },
    });

    const result = await authApi.loginWith2FA(data);

    expect(postMock).toHaveBeenCalledWith('/auth/token/2fa', data);
    expect(setStoredTokenMock).toHaveBeenCalledWith('tfa-tok');
    expect(result.data).toEqual(mockUser);
  });

  it('setup2FA POSTs /auth/2fa/setup with no body', async () => {
    postMock.mockResolvedValueOnce({
      data: { secret: 'SECRETABC', otpauth_url: 'otpauth://x', qr_code: 'qr' },
    });

    const result = await authApi.setup2FA();

    expect(postMock).toHaveBeenCalledWith('/auth/2fa/setup');
    expect(result.data.secret).toBe('SECRETABC');
  });

  it('verify2FA POSTs /auth/2fa/verify with the TOTPVerifyRequest body', async () => {
    const data = { otp: '123456' };
    postMock.mockResolvedValueOnce({ data: { success: true } });

    const result = await authApi.verify2FA(data);

    expect(postMock).toHaveBeenCalledWith('/auth/2fa/verify', data);
    expect(result.data).toEqual({ success: true });
  });

  it('disable2FA POSTs /auth/2fa/disable with the TOTPDisableRequest body', async () => {
    const data = { password: 'pw', otp: '123456' };
    postMock.mockResolvedValueOnce({ data: { message: 'disabled' } });

    const result = await authApi.disable2FA(data);

    expect(postMock).toHaveBeenCalledWith('/auth/2fa/disable', data);
    expect(result.data['message']).toBe('disabled');
  });
});

describe('authApi — email verification & password reset', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('verifyEmail POSTs /auth/verify-email with the body', async () => {
    const data = { email: 'x@y.z' };
    postMock.mockResolvedValueOnce({ data: { message: 'sent' } });

    const result = await authApi.verifyEmail(data);

    expect(postMock).toHaveBeenCalledWith('/auth/verify-email', data);
    expect(result.data['message']).toBe('sent');
  });

  it('verifyEmailConfirm GETs /auth/verify-email/confirm with token param', async () => {
    getMock.mockResolvedValueOnce({ data: { message: 'verified' } });

    const result = await authApi.verifyEmailConfirm('confirm-token-xyz');

    expect(getMock).toHaveBeenCalledWith('/auth/verify-email/confirm', {
      params: { token: 'confirm-token-xyz' },
    });
    expect(result.data['message']).toBe('verified');
  });

  it('resetPassword POSTs /auth/reset-password with the body', async () => {
    const data = { email: 'x@y.z' };
    postMock.mockResolvedValueOnce({ data: { message: 'sent' } });

    await authApi.resetPassword(data);

    expect(postMock).toHaveBeenCalledWith('/auth/reset-password', data);
  });

  it('resetPasswordConfirm POSTs /auth/reset-password/confirm with {token, new_password}', async () => {
    postMock.mockResolvedValueOnce({ data: { message: 'reset' } });

    const result = await authApi.resetPasswordConfirm('reset-tok', {
      password: 'newpw',
    });

    expect(postMock).toHaveBeenCalledWith('/auth/reset-password/confirm', {
      token: 'reset-tok',
      new_password: { password: 'newpw' },
    });
    expect(result.data['message']).toBe('reset');
  });
});

describe('authApi — logout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('logout POSTs /auth/logout and calls removeStoredToken after success', async () => {
    postMock.mockResolvedValueOnce({ data: { message: 'logged out' } });

    await authApi.logout();

    expect(postMock).toHaveBeenCalledWith('/auth/logout');
    expect(removeStoredTokenMock).toHaveBeenCalledTimes(1);
  });
});

describe('authApi — WebAuthn', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('webauthnRegisterOptions POSTs /auth/webauthn/register/options with nickname body', async () => {
    postMock.mockResolvedValueOnce({
      data: { options: {}, challenge_token: 'chal-1' },
    });

    await authApi.webauthnRegisterOptions('my-key');

    expect(postMock).toHaveBeenCalledWith('/auth/webauthn/register/options', {
      nickname: 'my-key',
    });
  });

  it('webauthnRegisterVerify POSTs /auth/webauthn/register/verify with the full body', async () => {
    const body = {
      challenge_token: 'chal-1',
      credential: { id: 'cred', response: {} },
      nickname: 'my-key',
    };
    postMock.mockResolvedValueOnce({
      data: {
        id: 'cred-id',
        nickname: 'my-key',
        backup_eligible: false,
        backup_state: false,
        created_at: '2026-04-24T00:00:00Z',
      },
    });

    await authApi.webauthnRegisterVerify(body);

    expect(postMock).toHaveBeenCalledWith(
      '/auth/webauthn/register/verify',
      body
    );
  });

  it('webauthnLoginOptions POSTs /auth/webauthn/login/options with optional username', async () => {
    postMock.mockResolvedValueOnce({
      data: { options: {}, challenge_token: 'chal-2' },
    });

    await authApi.webauthnLoginOptions('someone');

    expect(postMock).toHaveBeenCalledWith('/auth/webauthn/login/options', {
      username: 'someone',
    });
  });

  it('webauthnLoginOptions passes undefined username when not provided', async () => {
    postMock.mockResolvedValueOnce({
      data: { options: {}, challenge_token: 'chal-3' },
    });

    await authApi.webauthnLoginOptions();

    expect(postMock).toHaveBeenCalledWith('/auth/webauthn/login/options', {
      username: undefined,
    });
  });

  it('webauthnLoginVerify POSTs /auth/webauthn/login/verify, stores token, unwraps user', async () => {
    const body = {
      challenge_token: 'chal-4',
      credential: { id: 'cred', response: {} },
    };
    postMock.mockResolvedValueOnce({
      data: {
        access_token: 'webauthn-tok',
        token_type: 'bearer',
        user: mockUser,
      },
    });

    const result = await authApi.webauthnLoginVerify(body);

    expect(postMock).toHaveBeenCalledWith('/auth/webauthn/login/verify', body);
    expect(setStoredTokenMock).toHaveBeenCalledWith('webauthn-tok');
    expect(result.data).toEqual(mockUser);
  });

  it('webauthnListCredentials GETs /auth/webauthn/credentials', async () => {
    getMock.mockResolvedValueOnce({ data: [] });

    await authApi.webauthnListCredentials();

    expect(getMock).toHaveBeenCalledWith('/auth/webauthn/credentials');
  });

  it('webauthnRenameCredential PATCHes /auth/webauthn/credentials/:id with nickname body', async () => {
    patchMock.mockResolvedValueOnce({
      data: {
        id: 'abc-id',
        nickname: 'new',
        backup_eligible: false,
        backup_state: false,
        created_at: '2026-04-24T00:00:00Z',
      },
    });

    await authApi.webauthnRenameCredential('abc-id', 'new');

    expect(patchMock).toHaveBeenCalledWith(
      '/auth/webauthn/credentials/abc-id',
      { nickname: 'new' }
    );
  });

  it('webauthnDeleteCredential DELETEs /auth/webauthn/credentials/:id', async () => {
    deleteMock.mockResolvedValueOnce({ data: { message: 'deleted' } });

    await authApi.webauthnDeleteCredential('abc-id');

    expect(deleteMock).toHaveBeenCalledWith(
      '/auth/webauthn/credentials/abc-id'
    );
  });
});

describe('authApi — Google OAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('googleSignIn POSTs /auth/oauth/google with the GoogleSignInRequest body', async () => {
    const data = { id_token: 'google-id-token', nonce: 'n-1' };
    postMock.mockResolvedValueOnce({
      data: { status: 'token', access_token: 'g-tok', user: mockUser },
    });

    await authApi.googleSignIn(data);

    expect(postMock).toHaveBeenCalledWith('/auth/oauth/google', data);
  });

  it('googleLink POSTs /auth/oauth/google/link, stores token, unwraps user', async () => {
    const data = {
      link_token: 'link-token-xyz',
      password: 'pw',
    };
    postMock.mockResolvedValueOnce({
      data: {
        access_token: 'glink-tok',
        token_type: 'bearer',
        user: mockUser,
      },
    });

    const result = await authApi.googleLink(data);

    expect(postMock).toHaveBeenCalledWith('/auth/oauth/google/link', data);
    expect(setStoredTokenMock).toHaveBeenCalledWith('glink-tok');
    expect(result.data).toEqual(mockUser);
  });

  it('googleSignup POSTs /auth/oauth/google/signup, stores token, unwraps user', async () => {
    const data = { signup_token: 'signup-token-xyz', username: 'newuser' };
    postMock.mockResolvedValueOnce({
      data: {
        access_token: 'gsignup-tok',
        token_type: 'bearer',
        user: mockUser,
      },
    });

    const result = await authApi.googleSignup(data);

    expect(postMock).toHaveBeenCalledWith('/auth/oauth/google/signup', data);
    expect(setStoredTokenMock).toHaveBeenCalledWith('gsignup-tok');
    expect(result.data).toEqual(mockUser);
  });

  it('oauthTwoFactor POSTs /auth/oauth/2fa, stores token, unwraps user', async () => {
    const data = { otp_token: 'otp-tok', otp: '123456' };
    postMock.mockResolvedValueOnce({
      data: {
        access_token: 'otfa-tok',
        token_type: 'bearer',
        user: mockUser,
      },
    });

    const result = await authApi.oauthTwoFactor(data);

    expect(postMock).toHaveBeenCalledWith('/auth/oauth/2fa', data);
    expect(setStoredTokenMock).toHaveBeenCalledWith('otfa-tok');
    expect(result.data).toEqual(mockUser);
  });

  it('googleConnect POSTs /auth/oauth/google/connect with the body', async () => {
    const data = { id_token: 'google-id-token', nonce: 'n-2' };
    postMock.mockResolvedValueOnce({
      data: {
        id: 'oauth-1',
        provider: 'google',
        provider_user_id: 'g-uid',
        email: 'x@y.z',
        created_at: '2026-04-24T00:00:00Z',
      },
    });

    await authApi.googleConnect(data);

    expect(postMock).toHaveBeenCalledWith('/auth/oauth/google/connect', data);
  });

  it('listOAuthAccounts GETs /auth/oauth', async () => {
    getMock.mockResolvedValueOnce({ data: [] });

    await authApi.listOAuthAccounts();

    expect(getMock).toHaveBeenCalledWith('/auth/oauth');
  });

  it('deleteOAuthAccount DELETEs /auth/oauth/:id', async () => {
    deleteMock.mockResolvedValueOnce({ data: { message: 'deleted' } });

    await authApi.deleteOAuthAccount('oauth-1');

    expect(deleteMock).toHaveBeenCalledWith('/auth/oauth/oauth-1');
  });
});
