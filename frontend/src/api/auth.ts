// Auth domain API. Mirrors backend endpoints/auth/*.
//
// WebAuthn helper response types are co-located here (D-04) — they are not
// pydantic-generated and only consumed by the auth flow.
import type { AxiosResponse } from 'axios';
import { apiClient, setStoredToken, removeStoredToken } from './client';
import type {
  BodyLoginForAccessToken,
  BodyResetPassword,
  BodyVerifyEmail,
  GoogleConnectRequest,
  GoogleLinkRequest,
  GoogleSignInRequest,
  GoogleSignInResponse,
  GoogleSignupRequest,
  LoginResponse,
  NewPassword,
  OAuthAccountRead,
  OAuthTwoFactorRequest,
  TOTPDisableRequest,
  TOTPLoginRequest,
  TOTPSetupResponse,
  TOTPVerifyRequest,
  TOTPVerifyResponse,
  UserRead,
} from '../types/Api';

export interface WebAuthnOptionsResponse {
  options: Record<string, unknown>;
  challenge_token: string;
}

export interface WebAuthnCredentialSummary {
  id: string;
  nickname: string;
  aaguid?: string | null;
  transports?: string[] | null;
  backup_eligible: boolean;
  backup_state: boolean;
  created_at: string;
  last_used_at?: string | null;
}

export const authApi = {
  login: async (
    data: BodyLoginForAccessToken
  ): Promise<AxiosResponse<UserRead | LoginResponse>> => {
    const response = await apiClient.post<LoginResponse>('/auth/token', data, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    // If 2FA is required, return the response as-is
    if (response.data.requires_2fa) {
      return response;
    }
    // Store the token
    if (response.data.access_token) {
      setStoredToken(response.data.access_token);
    }
    // Enforce the contract: non-2FA login MUST return a user payload.
    // Previously `response.data.user!` silently produced AxiosResponse<UserRead>
    // whose .data was `undefined`, causing confusing downstream crashes.
    if (!response.data.user) {
      throw new Error(
        'Login response missing user payload (server contract violation)'
      );
    }
    // Return response with user data as the main data field
    return {
      ...response,
      data: response.data.user,
    } as AxiosResponse<UserRead>;
  },
  loginWith2FA: async (
    data: TOTPLoginRequest
  ): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/token/2fa', data);
    // Store the token
    if (response.data.access_token) {
      setStoredToken(response.data.access_token);
    }
    // Return response with user data as the main data field
    return {
      ...response,
      data: response.data.user,
    } as AxiosResponse<UserRead>;
  },
  setup2FA: () => apiClient.post<TOTPSetupResponse>('/auth/2fa/setup'),
  verify2FA: (data: TOTPVerifyRequest) =>
    apiClient.post<TOTPVerifyResponse>('/auth/2fa/verify', data),
  disable2FA: (data: TOTPDisableRequest) =>
    apiClient.post<Record<string, string>>('/auth/2fa/disable', data),
  verifyEmail: (data: BodyVerifyEmail) =>
    apiClient.post<Record<string, string>>('/auth/verify-email', data),
  verifyEmailConfirm: (token: string) =>
    apiClient.get<Record<string, string>>('/auth/verify-email/confirm', {
      params: { token },
    }),
  resetPassword: (data: BodyResetPassword) =>
    apiClient.post<Record<string, string>>('/auth/reset-password', data),
  resetPasswordConfirm: (token: string, data: NewPassword) =>
    apiClient.post<Record<string, string>>('/auth/reset-password/confirm', {
      token,
      new_password: data,
    }),
  logout: async () => {
    const response =
      await apiClient.post<Record<string, string>>('/auth/logout');
    // Remove token from storage
    removeStoredToken();
    return response;
  },

  webauthnRegisterOptions: (nickname: string) =>
    apiClient.post<WebAuthnOptionsResponse>('/auth/webauthn/register/options', {
      nickname,
    }),
  webauthnRegisterVerify: (data: {
    challenge_token: string;
    credential: unknown;
    nickname: string;
  }) =>
    apiClient.post<WebAuthnCredentialSummary>(
      '/auth/webauthn/register/verify',
      data
    ),
  webauthnLoginOptions: (username?: string) =>
    apiClient.post<WebAuthnOptionsResponse>('/auth/webauthn/login/options', {
      username,
    }),
  webauthnLoginVerify: async (data: {
    challenge_token: string;
    credential: unknown;
  }): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/webauthn/login/verify', data);
    if (response.data.access_token) {
      setStoredToken(response.data.access_token);
    }
    return {
      ...response,
      data: response.data.user,
    } as AxiosResponse<UserRead>;
  },
  webauthnListCredentials: () =>
    apiClient.get<WebAuthnCredentialSummary[]>('/auth/webauthn/credentials'),
  webauthnRenameCredential: (id: string, nickname: string) =>
    apiClient.patch<WebAuthnCredentialSummary>(
      `/auth/webauthn/credentials/${id}`,
      { nickname }
    ),
  webauthnDeleteCredential: (id: string) =>
    apiClient.delete<Record<string, string>>(
      `/auth/webauthn/credentials/${id}`
    ),

  // Google sign-in. The first call returns one of four shapes (token / 2fa / link
  // required / signup required); the caller dispatches on the discriminator. Token
  // storage happens in the page handler so the merge / signup flows can complete first.
  googleSignIn: (data: GoogleSignInRequest) =>
    apiClient.post<GoogleSignInResponse>('/auth/oauth/google', data),
  googleLink: async (
    data: GoogleLinkRequest
  ): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/oauth/google/link', data);
    if (response.data.access_token) setStoredToken(response.data.access_token);
    return { ...response, data: response.data.user } as AxiosResponse<UserRead>;
  },
  googleSignup: async (
    data: GoogleSignupRequest
  ): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/oauth/google/signup', data);
    if (response.data.access_token) setStoredToken(response.data.access_token);
    return { ...response, data: response.data.user } as AxiosResponse<UserRead>;
  },
  oauthTwoFactor: async (
    data: OAuthTwoFactorRequest
  ): Promise<AxiosResponse<UserRead>> => {
    const response = await apiClient.post<{
      access_token: string;
      token_type: string;
      user: UserRead;
    }>('/auth/oauth/2fa', data);
    if (response.data.access_token) setStoredToken(response.data.access_token);
    return { ...response, data: response.data.user } as AxiosResponse<UserRead>;
  },
  googleConnect: (data: GoogleConnectRequest) =>
    apiClient.post<OAuthAccountRead>('/auth/oauth/google/connect', data),
  listOAuthAccounts: () => apiClient.get<OAuthAccountRead[]>('/auth/oauth'),
  deleteOAuthAccount: (id: string) =>
    apiClient.delete<Record<string, string>>(`/auth/oauth/${id}`),
};
