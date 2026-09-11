/**
 * The "Sign in with a passkey" button for identity mode.
 *
 * Mirrors WebbPulse-Portfolio's `components/admin/PasskeySignInButton.tsx`.
 *
 * ## Why the button can be absent
 *
 * Three separate things have to be true before a passwordless sign in can work,
 * and they fail in different places:
 *
 *   1. the browser has to support WebAuthn at all (`passkeysSupported`)
 *   2. the deployment has to have passwordless sign in switched on, which the
 *      discovery route states as a field (`passkeyLoginAvailability`)
 *   3. the user has to actually have a passkey, which nothing can know before
 *      the ceremony runs
 *
 * The first two hide the button. The third cannot: asking would mean
 * enumerating accounts. So a user with no passkey sees the button, presses it,
 * and the browser tells them there is nothing to use, which is the browser's
 * job and not this component's.
 *
 * Nothing is rendered while the route is in flight. A button that appears and
 * then vanishes is worse than one that appears a beat late, and the password
 * form above it is usable the whole time.
 *
 * ## Conditional mediation
 *
 * `mediation: 'conditional'` puts the account chooser inside the username
 * field's own autofill rather than in a modal sheet, so a user who has a passkey
 * sees it offered as they focus the field and one who does not sees nothing at
 * all. It runs on mount alongside the visible button and is aborted on unmount:
 * a conditional request that outlives its page keeps the authenticator armed
 * against a form that is gone.
 *
 * A conditional request that finds no credential never resolves, which is why
 * its failure path is silence rather than an error banner.
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
        // `unknown` hides the button too: a read that learned nothing should
        // not produce an affordance whose failure the user cannot act on.
        setAvailable(answer === 'available');
      }
    );
    return () => {
      live = false;
    };
  }, [supported]);

  // Conditional mediation, armed once the deployment is known to support it.
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
      // A dismissed sheet is not an error and gets no banner.
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
