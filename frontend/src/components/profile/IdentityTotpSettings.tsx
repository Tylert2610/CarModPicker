/**
 * The TOTP panel for identity mode: enrol, disable, and replace recovery codes.
 *
 * Modelled on WebbPulse-Portfolio's `components/admin/SecuritySection.tsx`,
 * which serves the same three operations against the same package.
 *
 * ## Why this is a separate component from the existing 2FA tab
 *
 * The tab this replaces is not a different rendering of the same flow, it is a
 * different flow. The legacy one takes the account password alongside the code
 * to disable a factor, gets a `secret` and a data-URI QR image from the server,
 * and issues no recovery codes because the legacy service has none. The
 * identity service takes only a code (the fresh code *is* the proof), returns a
 * provisioning URI for the client to render, and issues ten single use recovery
 * codes on activation that are shown exactly once.
 *
 * Trying to hold both in one component would mean a mode branch at every field,
 * every call and every piece of copy. Two components with one switch at the top
 * is smaller, and the legacy one is deleted whole when the cutover finishes
 * rather than being unpicked from this one.
 *
 * ## Why the recovery codes are behind a confirmation
 *
 * They are shown once and never again: the server stores hashes. A user who
 * closes the panel without saving them has lost their only way back into an
 * account whose authenticator is on a lost phone. The checkbox is what makes
 * dismissing them a deliberate act rather than a stray click.
 */
import React, { useState } from 'react';
import { FaShieldAlt } from 'react-icons/fa';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { getIdentityClient } from '../../api/identityClient';
import { qrCodeSvgPath } from '../../utils/qrCode';

/** Where the panel is in the enrolment flow. */
type Step =
  | { kind: 'idle' }
  | { kind: 'enrolling'; secret: string; provisioningUri: string }
  | { kind: 'codes'; codes: string[] };

/**
 * The sentence for each refusal the package models.
 *
 * The server's own message wins where it has one. Every refusal a user can
 * reach with a form open in front of them is here, because a form that shows
 * "an error occurred" for a mistyped code is a form that teaches nothing.
 */
const REFUSAL_FALLBACKS: Record<string, string> = {
  'invalid-code':
    'That code was not accepted. Check your authenticator app and try the current code.',
  'already-enabled':
    'Two factor authentication is already on for this account.',
  'no-pending-enrolment':
    'That enrolment expired. Start again to get a fresh QR code.',
  'rate-limited': 'Too many attempts. Wait a few minutes and try again.',
  unavailable:
    'Two factor authentication is not configured for this deployment.',
};

/** Reads the message off any refusal the package returns. */
const refusalMessage = (outcome: { reason: string; message: string }): string =>
  outcome.message ||
  REFUSAL_FALLBACKS[outcome.reason] ||
  'That request could not be completed.';

/** The provisioning URI as a scannable QR code. */
const ProvisioningQr: React.FC<{ uri: string }> = ({ uri }) => {
  let path: { path: string; size: number };
  try {
    path = qrCodeSvgPath(uri);
  } catch {
    // A URI too long for version 10 at level M. The secret below is the
    // fallback every authenticator accepts, so the panel stays usable.
    return null;
  }
  return (
    <svg
      viewBox={`0 0 ${String(path.size)} ${String(path.size)}`}
      className="w-48 h-48 bg-white p-2 rounded-lg"
      role="img"
      aria-label="Two factor authentication QR code"
    >
      <path d={path.path} fill="#000000" />
    </svg>
  );
};

/** The one-time recovery codes, behind a confirmation. */
const RecoveryCodes: React.FC<{ codes: string[]; onDone: () => void }> = ({
  codes,
  onDone,
}) => {
  const [saved, setSaved] = useState(false);
  return (
    <div className="space-y-4">
      <ConfirmationAlert message="Two factor authentication is on. Save these recovery codes now." />
      <p className="text-sm text-gray-400">
        Each code signs you in once if you lose your authenticator app. They are
        shown here and nowhere else, because the server keeps only hashes of
        them. Store them somewhere you can reach without this account.
      </p>
      <ul className="grid grid-cols-2 gap-2 bg-gray-800/50 rounded-lg p-4 font-mono text-sm text-gray-200">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <label className="flex items-center gap-2 text-sm text-gray-300">
        <input
          type="checkbox"
          checked={saved}
          onChange={(e) => setSaved(e.target.checked)}
        />
        <span>I have saved these codes somewhere safe.</span>
      </label>
      <Button
        type="button"
        className="w-full"
        disabled={!saved}
        onClick={onDone}
      >
        Done
      </Button>
    </div>
  );
};

interface Props {
  /** True when the account already has a factor, from `UserRead.totp_enabled`. */
  enabled: boolean;
  /** Called after a change so the caller can refetch the user. */
  onChanged: () => void;
}

const IdentityTotpSettings: React.FC<Props> = ({ enabled, onChanged }) => {
  const [step, setStep] = useState<Step>({ kind: 'idle' });
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const identity = getIdentityClient();
  if (identity === null) {
    return (
      <ErrorAlert message="Two factor authentication is not available in this deployment." />
    );
  }

  const reset = () => {
    setStep({ kind: 'idle' });
    setCode('');
    setError(null);
  };

  const handleEnrol = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const outcome = await identity.enrolTotp();
      if (outcome.ok) {
        setStep({
          kind: 'enrolling',
          secret: outcome.secret,
          provisioningUri: outcome.provisioningUri,
        });
      } else {
        setError(refusalMessage(outcome));
      }
    } catch {
      setError('Could not reach the server. Check your connection.');
    } finally {
      setBusy(false);
    }
  };

  const handleActivate = async () => {
    setBusy(true);
    setError(null);
    try {
      const outcome = await identity.activateTotp({ code: code.trim() });
      if (outcome.ok) {
        setStep({ kind: 'codes', codes: outcome.recoveryCodes });
        setCode('');
        onChanged();
      } else {
        setError(refusalMessage(outcome));
      }
    } catch {
      setError('Could not reach the server. Check your connection.');
    } finally {
      setBusy(false);
    }
  };

  const handleDisable = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const outcome = await identity.disableTotp({ code: code.trim() });
      if (outcome.ok) {
        setSuccess('Two factor authentication is off.');
        setCode('');
        onChanged();
      } else {
        setError(refusalMessage(outcome));
      }
    } catch {
      setError('Could not reach the server. Check your connection.');
    } finally {
      setBusy(false);
    }
  };

  const handleRegenerate = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const outcome = await identity.regenerateRecoveryCodes({
        code: code.trim(),
      });
      if (outcome.ok) {
        setStep({ kind: 'codes', codes: outcome.recoveryCodes });
        setCode('');
      } else {
        setError(refusalMessage(outcome));
      }
    } catch {
      setError('Could not reach the server. Check your connection.');
    } finally {
      setBusy(false);
    }
  };

  if (step.kind === 'codes') {
    return (
      <RecoveryCodes
        codes={step.codes}
        onDone={() => {
          setStep({ kind: 'idle' });
          setSuccess('Recovery codes saved.');
        }}
      />
    );
  }

  const codeField = (
    label: string,
    id: string,
    hint: string
  ): React.ReactElement => (
    <div>
      <label
        htmlFor={id}
        className="block text-sm font-medium text-foreground mb-2"
      >
        {label}
      </label>
      <Input
        id={id}
        name={id}
        type="text"
        autoComplete="one-time-code"
        inputMode="text"
        value={code}
        onChange={(e) => setCode(e.target.value.slice(0, 32))}
        placeholder="Code"
        disabled={busy}
      />
      <p className="mt-1 text-xs text-gray-400">{hint}</p>
    </div>
  );

  return (
    <div className="space-y-6">
      {success !== null && <ConfirmationAlert message={success} />}
      {error !== null && <ErrorAlert message={error} />}

      <div className="flex items-center space-x-3 text-gray-300">
        <FaShieldAlt className="text-primary text-2xl" />
        <div>
          <h3 className="text-lg font-semibold">Two-Factor Authentication</h3>
          <p className="text-sm text-gray-400">
            {enabled
              ? 'Your account asks for a code from your authenticator app when you sign in.'
              : 'Ask for a code from your authenticator app when you sign in.'}
          </p>
        </div>
      </div>

      {step.kind === 'enrolling' && (
        <div className="space-y-4">
          <p className="text-sm text-gray-300">
            Scan this with your authenticator app, then enter the code it shows
            to finish turning it on.
          </p>
          <div className="flex justify-center">
            <ProvisioningQr uri={step.provisioningUri} />
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <p className="text-xs text-gray-400 mb-1">
              Cannot scan? Enter this key by hand instead.
            </p>
            <code className="font-mono text-sm text-gray-200 break-all">
              {step.secret}
            </code>
          </div>
          {codeField(
            'Code from your app',
            'totp-activate',
            'Six digits, from the app you just scanned into.'
          )}
          <div className="flex gap-3">
            <Button
              type="button"
              className="flex-1"
              onClick={() => void handleActivate()}
              disabled={busy || code.trim() === ''}
              loading={busy}
            >
              Turn on
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="flex-1"
              onClick={reset}
              disabled={busy}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {step.kind === 'idle' && !enabled && (
        <Button
          type="button"
          className="w-full"
          onClick={() => void handleEnrol()}
          disabled={busy}
          loading={busy}
        >
          Set up two-factor authentication
        </Button>
      )}

      {step.kind === 'idle' && enabled && (
        <div className="space-y-4">
          {codeField(
            'Current code',
            'totp-verify',
            'A code from your authenticator app, or one of your recovery codes. The current code is the proof, so no password is needed.'
          )}
          <div className="flex flex-col gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void handleRegenerate()}
              disabled={busy || code.trim() === ''}
            >
              Replace recovery codes
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => void handleDisable()}
              disabled={busy || code.trim() === ''}
            >
              Turn off two-factor authentication
            </Button>
          </div>
          <p className="text-xs text-gray-400">
            Replacing recovery codes invalidates every code you were issued
            before.
          </p>
        </div>
      )}
    </div>
  );
};

export default IdentityTotpSettings;
