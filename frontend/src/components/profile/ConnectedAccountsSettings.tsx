import { useEffect, useMemo, useState } from 'react';
import { GoogleLogin, type CredentialResponse } from '@react-oauth/google';
import { FaGoogle, FaTrash } from 'react-icons/fa';
import { authApi } from '../../api/auth';
import { isGoogleConfigured } from '../../hooks/useGoogleSignIn';
import type { OAuthAccountRead } from '../../types/Api';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import Spinner from '../ui/spinner';

const formatDate = (value?: string | null): string => {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
};

const makeNonce = (): string => {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
};

const errMessage = (err: unknown, fallback: string): string => {
  const ax = err as {
    response?: { data?: { detail?: string; message?: string } };
  };
  return ax.response?.data?.message || ax.response?.data?.detail || fallback;
};

function ConnectedAccountsSettings() {
  const [accounts, setAccounts] = useState<OAuthAccountRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const nonce = useMemo(makeNonce, []);
  const googleEnabled = isGoogleConfigured();

  const load = async () => {
    try {
      const resp = await authApi.listOAuthAccounts();
      setAccounts(resp.data);
    } catch (err) {
      setError(errMessage(err, 'Failed to load connected accounts.'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const hasGoogle = accounts.some((a) => a.provider === 'google');

  const handleGoogleCredential = async (resp: CredentialResponse) => {
    setError(null);
    setSuccess(null);
    if (!resp.credential) {
      setError('Google did not return a credential. Please try again.');
      return;
    }
    setBusy(true);
    try {
      await authApi.googleConnect({ id_token: resp.credential, nonce });
      setSuccess('Google account connected.');
      await load();
    } catch (err) {
      setError(errMessage(err, 'Could not connect Google account.'));
    } finally {
      setBusy(false);
    }
  };

  const handleDisconnect = async (id: string) => {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      await authApi.deleteOAuthAccount(id);
      setSuccess('Connected account removed.');
      await load();
    } catch (err) {
      setError(errMessage(err, 'Could not remove connected account.'));
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-6">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {success && <ConfirmationAlert message={success} />}
      {error && <ErrorAlert message={error} />}

      {!googleEnabled && (
        <div className="bg-gray-800/50 rounded-lg p-4 text-sm text-gray-400">
          Google sign-in is not enabled in this environment.
        </div>
      )}

      {accounts.length === 0 ? (
        <p className="text-sm text-gray-400">
          No third-party sign-in methods are linked to your account yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {accounts.map((acc) => (
            <li
              key={acc.id}
              className="flex items-center justify-between bg-gray-800/50 rounded-lg p-4"
            >
              <div className="flex items-center gap-3">
                {acc.provider === 'google' ? (
                  <FaGoogle className="text-primary text-xl" />
                ) : (
                  <span className="text-primary text-xl">●</span>
                )}
                <div>
                  <div className="font-medium text-gray-200 capitalize">
                    {acc.provider}
                  </div>
                  <div className="text-xs text-gray-400">
                    {acc.email || '—'} • linked {formatDate(acc.created_at)}
                  </div>
                </div>
              </div>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void handleDisconnect(acc.id)}
                disabled={busy}
              >
                <FaTrash />
                Disconnect
              </Button>
            </li>
          ))}
        </ul>
      )}

      {googleEnabled && !hasGoogle && (
        <div className="pt-2 flex justify-center">
          <GoogleLogin
            onSuccess={(resp) => void handleGoogleCredential(resp)}
            onError={() => setError('Google sign-in was cancelled or failed.')}
            nonce={nonce}
            theme="filled_black"
            shape="pill"
            text="continue_with"
            width="320"
            useOneTap={false}
          />
        </div>
      )}
    </div>
  );
}

export default ConnectedAccountsSettings;
