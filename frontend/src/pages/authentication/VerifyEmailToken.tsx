/**
 * Landing page for a mailed verification link in identity mode.
 *
 * Mounted by `VerifyEmail` only for the `?token=` branch of `/verify-email`.
 * The token is single use, so a ref guards the mount effect against the double
 * invocation React strict mode performs in development.
 */
import { useEffect, useRef, useState } from 'react';
import {
  LINK_TOKEN_PARAM,
  VERIFY_EMAIL_PATH,
  readLinkToken,
} from '@webbpulse/auth';
import AuthCard from '../../components/auth/AuthCard';
import AuthRedirectLink from '../../components/auth/AuthRedirectLink';
import { ConfirmationAlert, ErrorAlert } from '../../components/ui/alert';
import Spinner from '../../components/ui/spinner';
import { getIdentityClient } from '../../api/identityClient';
import { useAuth } from '../../hooks/useAuth';

/** What the page is showing. */
type State =
  | { kind: 'confirming' }
  | { kind: 'confirmed' }
  | { kind: 'refused'; message: string }
  | { kind: 'unavailable' };

/**
 * Fallback sentence for each refusal the package models, used when the server
 * sends no message of its own. Each one names the user's next step.
 */
const REFUSAL_FALLBACKS: Record<string, string> = {
  'invalid-link':
    'This link is no longer valid. Verification links expire and can only be used once. Sign in and request a new one.',
  'rate-limited':
    'Too many attempts. Wait a few minutes, then request a new verification link.',
  unavailable:
    'Email is not configured for this deployment, so verification links cannot be sent. Contact support.',
};

/** Spends a mailed verification token once on mount and reports the outcome. */
function VerifyEmailToken() {
  const [state, setState] = useState<State>({ kind: 'confirming' });
  const spent = useRef(false);
  const { checkAuthStatus } = useAuth();

  useEffect(() => {
    if (spent.current) return;
    spent.current = true;

    const identity = getIdentityClient();
    if (identity === null) {
      setState({ kind: 'unavailable' });
      return;
    }
    const token = readLinkToken({ expectedPath: VERIFY_EMAIL_PATH });
    if (token === null) {
      setState({
        kind: 'refused',
        message: 'This link is missing its token. Request a new one.',
      });
      return;
    }

    const confirm = async () => {
      try {
        const outcome = await identity.confirmEmailVerification({ token });
        if (outcome.ok) {
          setState({ kind: 'confirmed' });
          await checkAuthStatus();
          return;
        }
        setState({
          kind: 'refused',
          message:
            outcome.message ||
            REFUSAL_FALLBACKS[outcome.reason] ||
            'This verification link could not be used.',
        });
      } catch {
        setState({
          kind: 'refused',
          message:
            'Could not reach the server to verify your email. Check your connection and try the link again.',
        });
      }
    };
    void confirm();
  }, [checkAuthStatus]);

  if (state.kind === 'confirming') {
    return (
      <AuthCard title="Verifying your email">
        <Spinner />
      </AuthCard>
    );
  }

  if (state.kind === 'confirmed') {
    return (
      <AuthCard title="Email verified">
        <ConfirmationAlert message="Your email address is verified. You can use every part of your account now." />
        <AuthRedirectLink text="Go to" linkText="Profile" to="/profile" />
      </AuthCard>
    );
  }

  if (state.kind === 'unavailable') {
    return (
      <AuthCard title="Verify your email">
        <ErrorAlert message="Email verification is not available in this deployment." />
        <AuthRedirectLink text="Proceed to" linkText="Sign In" to="/login" />
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Verification failed">
      <ErrorAlert message={state.message} />
      <AuthRedirectLink text="Proceed to" linkText="Sign In" to="/login" />
    </AuthCard>
  );
}

export { LINK_TOKEN_PARAM };
export default VerifyEmailToken;
