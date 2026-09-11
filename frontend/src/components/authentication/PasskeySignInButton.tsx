/**
 * The "Sign in with a passkey" button for identity mode, hidden unless the
 * browser supports WebAuthn and the deployment enables passwordless sign in.
 * Also arms conditional mediation so the chooser appears in username autofill.
 */
import { useEffect, useRef, useState } from 'react';
import { FaKey } from 'react-icons/fa';
import { Button } from '../ui/button';
import { identityUrl } from '../../api/identityClient';
import {
  PASSKEY_AVAILABILITY_PATH,
  passkeyLoginAvailability,
} from '../../api/passkeyAvailability';
import {
  passkeysSupported,
  signInWithPasskey,
  type PasskeySignInResult,
} from '../../api/identityPasskeys';

/**
 * Props for PasskeySignInButton: the username hint, outcome callback, and autofill flag.
 */
export interface PasskeySignInButtonProps {
  /** Whatever is in the username field, so a known user skips the chooser. */
  username?: string;
  /** Called for every outcome except a cancellation, which is silent. */
  onResult: (result: PasskeySignInResult) => void | Promise<void>;
  disabled?: boolean;
  /** Whether to arm conditional mediation on mount. Off in tests by default. */
  conditional?: boolean;
}

function PasskeySignInButton({
  username,
  onResult,
  disabled,
  conditional = true,
}: PasskeySignInButtonProps) {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const supported = passkeysSupported();
  const handler = useRef(onResult);
  handler.current = onResult;

  useEffect(() => {
    if (!supported) {
      setAvailable(false);
      return;
    }
    let live = true;
    void passkeyLoginAvailability(identityUrl(PASSKEY_AVAILABILITY_PATH)).then(
      (answer) => {
        if (!live) return;
        setAvailable(answer === 'available');
      }
    );
    return () => {
      live = false;
    };
  }, [supported]);

  useEffect(() => {
    if (!conditional || available !== true) return;
    const controller = new AbortController();
    void signInWithPasskey({
      mediation: 'conditional',
      signal: controller.signal,
    }).then((result) => {
      if (controller.signal.aborted) return;
      if (result.status === 'cancelled' || result.status === 'failed') return;
      void handler.current(result);
    });
    return () => {
      controller.abort();
    };
  }, [conditional, available]);

  if (available !== true) return null;

  const handleClick = async () => {
    setBusy(true);
    try {
      const result = await signInWithPasskey(
        username !== undefined && username.trim() !== ''
          ? { username, mediation: 'optional' }
          : { mediation: 'optional' }
      );
      if (result.status === 'cancelled') return;
      await handler.current(result);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      type="button"
      variant="secondary"
      size="lg"
      className="w-full"
      onClick={() => void handleClick()}
      disabled={disabled || busy}
    >
      <FaKey />
      <span>
        {busy ? 'Waiting for your passkey…' : 'Sign in with a passkey'}
      </span>
    </Button>
  );
}

export default PasskeySignInButton;
