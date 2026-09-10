/**
 * The page a mailed verification link lands on in identity mode.
 *
 * ## Why this shares a path with the request page
 *
 * `VERIFY_EMAIL_PATH` in `@webbpulse/auth` is `/verify-email`, and the backend
 * builds the mailed URL by concatenating it onto the frontend base, so the
 * landing path is fixed by a contract this application does not own.
 * CarModPicker already had a `/verify-email`, and it means something else: a
 * signed in user asking for a fresh verification email.
 *
 * Both behaviours have to live at that one path, and the query string is what
 * tells them apart. A URL carrying `?token=` came from an email and is a
 * confirmation; a bare `/verify-email` is a person who navigated there and
 * wants a link sent. `VerifyEmail` does the routing between the two, and this
 * component is only ever mounted for the token branch, which is why it does no
 * mode check of its own.
 *
 * ## Why the token is spent in an effect and guarded by a ref
 *
 * The token is single use and confirming it is the whole job of the page, so
 * there is no button to wait for. That puts the call in a mount effect, and
 * React's strict mode runs mount effects twice in development. The second run
 * would present an already spent token and the user would be told their link
 * was invalid, which is exactly the bug this page exists to avoid reporting.
 * A ref rather than state because it must not trigger a render and must be set
 * synchronously before the await.
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
 * The sentence for each refusal the package models.
 *
 * The server's own message is preferred where it has one, because it is written
 * to be read. These are the fallbacks, and each one names the next step rather
 * than only the problem: a user holding a dead link needs to know what to do,
 * not what happened.
 */
const REFUSAL_FALLBACKS: Record<string, string> = {
  'invalid-link':
    'This link is no longer valid. Verification links expire and can only be used once. Sign in and request a new one.',
  'rate-limited':
    'Too many attempts. Wait a few minutes, then request a new verification link.',
  unavailable:
    'Email is not configured for this deployment, so verification links cannot be sent. Contact support.',
};

function VerifyEmailToken() {
  const [state, setState] = useState<State>({ kind: 'confirming' });
  const spent = useRef(false);
  const { checkAuthStatus } = useAuth();

  useEffect(() => {
    // Strict mode runs this twice in development. The token is single use, so
    // the second run would spend nothing and report a dead link.
    if (spent.current) return;
    spent.current = true;

    const identity = getIdentityClient();
    if (identity === null) {
      setState({ kind: 'unavailable' });
      return;
    }
    // `expectedPath` guards against reading a reset token off this page and
    // presenting it to the verification endpoint, which the server refuses as
    // a wrong-purpose token.
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
          // The signed in user's `email_verified` just changed, and
          // `EmailVerifiedRoute` gates on it. Refetching here is what lets the
          // user go straight to their profile rather than bouncing back.
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
