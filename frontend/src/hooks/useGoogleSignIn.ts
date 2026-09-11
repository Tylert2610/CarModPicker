/**
 * Drives Google sign in and the follow up states it can require: linking an
 * existing account, completing signup, or a second factor.
 */

import { useCallback, useMemo, useState } from 'react';
import { GOOGLE_CLIENT_ID } from '../config/google';
import { authApi } from '../api/auth';
import type {
  GoogleSignInLinkRequired,
  GoogleSignInResponse,
  GoogleSignInSignupRequired,
  OAuthTwoFactorRequired,
  UserRead,
} from '../types/Api';
import { getApiErrorMessage } from '../utils/apiError';

/** Whether a Google client id is present, so callers can hide the button. */
export const isGoogleConfigured = (): boolean => Boolean(GOOGLE_CLIENT_ID);

const makeNonce = (): string => {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
};

type Pending =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'link'; payload: GoogleSignInLinkRequired }
  | { kind: 'signup'; payload: GoogleSignInSignupRequired }
  | { kind: 'twoFactor'; payload: OAuthTwoFactorRequired };

interface UseGoogleSignInOptions {
  onLoggedIn: (user: UserRead) => void;
  onError: (message: string) => void;
}

/** Runs Google sign in and surfaces whichever follow up step it requires. */
export const useGoogleSignIn = ({
  onLoggedIn,
  onError,
}: UseGoogleSignInOptions) => {
  const [state, setState] = useState<Pending>({ kind: 'idle' });
  const nonce = useMemo(makeNonce, []);

  const handleResponse = useCallback(
    (data: GoogleSignInResponse) => {
      if ('access_token' in data) {
        onLoggedIn(data.user);
        setState({ kind: 'idle' });
        return;
      }
      if ('requires_2fa' in data) {
        setState({ kind: 'twoFactor', payload: data });
        return;
      }
      if ('requires_link' in data) {
        setState({ kind: 'link', payload: data });
        return;
      }
      if ('requires_signup' in data) {
        setState({ kind: 'signup', payload: data });
        return;
      }
    },
    [onLoggedIn]
  );

  const submitCredential = useCallback(
    async (credential: string) => {
      setState({ kind: 'loading' });
      try {
        const resp = await authApi.googleSignIn({
          id_token: credential,
          nonce,
        });
        handleResponse(resp.data);
      } catch (err: unknown) {
        const message = getApiErrorMessage(err, 'Google sign-in failed.');
        onError(message);
        setState({ kind: 'idle' });
      }
    },
    [handleResponse, nonce, onError]
  );

  const reset = useCallback(() => setState({ kind: 'idle' }), []);

  return { state, nonce, submitCredential, reset };
};
