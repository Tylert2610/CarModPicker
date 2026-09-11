import { useEffect, useState } from 'react';
import { FaKey, FaPlus, FaTrash } from 'react-icons/fa';
import {
  browserSupportsWebAuthn,
  startRegistration,
} from '@simplewebauthn/browser';
import { authApi } from '../../api/auth';
import type { WebAuthnCredentialSummary } from '../../api/auth';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import Spinner from '../ui/spinner';
import { getApiErrorMessage } from '../../utils/apiError';

/** A date for display, falling back to the raw value rather than throwing. */
function formatDate(value?: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
}

/** The legacy passkeys tab, speaking the app's own WebAuthn routes. */
function PasskeySettings() {
  const [credentials, setCredentials] = useState<WebAuthnCredentialSummary[]>(
    []
  );
  const [isLoading, setIsLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newNickname, setNewNickname] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const browserSupported = browserSupportsWebAuthn();

  const loadCredentials = async () => {
    try {
      const resp = await authApi.webauthnListCredentials();
      setCredentials(resp.data);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Failed to load passkeys.'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadCredentials();
  }, []);

  const handleAdd = async () => {
    setError(null);
    setSuccess(null);
    const nickname = newNickname.trim();
    if (!nickname) {
      setError('Please give your passkey a name (e.g. "Laptop", "YubiKey").');
      return;
    }
    setIsRegistering(true);
    try {
      const optsResp = await authApi.webauthnRegisterOptions(nickname);
      const { options, challenge_token } = optsResp.data;
      const credential = await startRegistration({
        optionsJSON: options as unknown as Parameters<
          typeof startRegistration
        >[0]['optionsJSON'],
      });
      await authApi.webauthnRegisterVerify({
        challenge_token,
        credential,
        nickname,
      });
      setSuccess(`Passkey "${nickname}" added.`);
      setShowAddForm(false);
      setNewNickname('');
      await loadCredentials();
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'NotAllowedError') {
        setError('Registration was cancelled.');
      } else {
        setError(getApiErrorMessage(err, 'Failed to register passkey.'));
      }
    } finally {
      setIsRegistering(false);
    }
  };

  const handleDelete = async (id: string, nickname: string) => {
    setError(null);
    setSuccess(null);
    if (!window.confirm(`Remove passkey "${nickname}"?`)) return;
    try {
      await authApi.webauthnDeleteCredential(id);
      setSuccess(`Passkey "${nickname}" removed.`);
      await loadCredentials();
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Failed to remove passkey.'));
    }
  };

  if (!browserSupported) {
    return (
      <div className="space-y-4">
        <div className="flex items-center space-x-3 text-gray-300">
          <FaKey className="text-primary text-2xl" />
          <div>
            <h3 className="text-lg font-semibold">Passkeys</h3>
            <p className="text-sm text-gray-400">
              Your browser does not support passkeys. Try a recent version of
              Chrome, Safari, Edge, or Firefox.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {success && <ConfirmationAlert message={success} />}
      {error && <ErrorAlert message={error} />}

      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start space-x-3 text-gray-300">
          <FaKey className="text-primary text-2xl mt-1" />
          <div>
            <h3 className="text-lg font-semibold">Passkeys</h3>
            <p className="text-sm text-gray-400">
              Sign in without a password or 2FA code — your device or hardware
              key proves it's you. Passkeys bypass 2FA on sign-in.
            </p>
          </div>
        </div>
        {!showAddForm && (
          <Button
            type="button"
            onClick={() => {
              setShowAddForm(true);
              setError(null);
              setSuccess(null);
            }}
          >
            <FaPlus /> Add passkey
          </Button>
        )}
      </div>

      {showAddForm && (
        <div className="bg-gray-800/50 rounded-lg p-4 space-y-4">
          <div>
            <label
              htmlFor="passkey-nickname"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Passkey name
            </label>
            <div className="relative">
              <span
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/60"
              >
                <FaKey />
              </span>
              <Input
                id="passkey-nickname"
                name="nickname"
                type="text"
                value={newNickname}
                onChange={(e) => setNewNickname(e.target.value)}
                placeholder="e.g. Work laptop, YubiKey 5C"
                disabled={isRegistering}
                className="pl-10"
              />
            </div>
            <div className="mt-2 text-sm text-muted-foreground">
              This helps you identify it later when you have multiple.
            </div>
          </div>
          <div className="flex space-x-2">
            <Button
              type="button"
              onClick={() => void handleAdd()}
              disabled={isRegistering || !newNickname.trim()}
              loading={isRegistering}
              className="flex-1"
            >
              {isRegistering ? 'Waiting for your device…' : 'Create passkey'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setShowAddForm(false);
                setNewNickname('');
              }}
              disabled={isRegistering}
              className="flex-1"
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center space-x-2 text-gray-400">
          <Spinner inline />
          <span>Loading passkeys…</span>
        </div>
      ) : credentials.length === 0 ? (
        <p className="text-sm text-gray-400">
          You don't have any passkeys yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {credentials.map((cred) => (
            <li
              key={cred.id}
              className="flex items-center justify-between bg-gray-800/50 rounded-lg p-3"
            >
              <div>
                <div className="font-medium text-gray-200">{cred.nickname}</div>
                <div className="text-xs text-gray-500">
                  Added {formatDate(cred.created_at)} • Last used{' '}
                  {formatDate(cred.last_used_at)}
                </div>
              </div>
              <button
                type="button"
                onClick={() => void handleDelete(cred.id, cred.nickname)}
                className="text-red-400 hover:text-red-300 p-2"
                aria-label={`Remove ${cred.nickname}`}
                title="Remove passkey"
              >
                <FaTrash />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default PasskeySettings;
