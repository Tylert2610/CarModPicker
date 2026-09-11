/**
 * The connected accounts panel for identity mode: link and unlink providers.
 * Linking is a full-page navigation because the start route redirects to a host
 * that sends no CORS headers; the callback returns with a marker in the query.
 */
import { useCallback, useEffect, useState } from 'react';
import { FaGithub, FaGoogle, FaLink, FaTrash } from 'react-icons/fa';
import { GITHUB_PROVIDER, GOOGLE_PROVIDER } from '@webbpulse/auth';
import { ConfirmationAlert, ErrorAlert } from '../ui/alert';
import { Button } from '../ui/button';
import Spinner from '../ui/spinner';
import { identityUrl } from '../../api/identityClient';
import {
  listLinks,
  unlinkProvider,
  type OAuthLink,
} from '../../api/identityOAuth';
import {
  OAUTH_PROVIDERS_PATH,
  oauthProviders,
  type OAuthProvider,
} from '../../api/oauthProviders';
import { getIdentityClient } from '../../api/identityClient';

/** A date for display, falling back to the raw value rather than throwing. */
const formatDate = (value: string | undefined): string => {
  if (!value) return 'Unknown';
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
};

/** The provider's mark, where this build has one. */
const ProviderIcon: React.FC<{ provider: string }> = ({ provider }) => {
  if (provider === GOOGLE_PROVIDER) return <FaGoogle />;
  if (provider === GITHUB_PROVIDER) return <FaGithub />;
  return <FaLink />;
};

function IdentityConnectedAccounts() {
  const [providers, setProviders] = useState<OAuthProvider[]>([]);
  const [links, setLinks] = useState<OAuthLink[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [configured, current] = await Promise.all([
      oauthProviders(identityUrl(OAUTH_PROVIDERS_PATH)),
      listLinks(),
    ]);
    setProviders(configured);
    if (current.status === 'ok') {
      setLinks(current.links);
    } else {
      setError(current.error);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /**
   * Starts a link by leaving the page; `returnTo` brings the user back here,
   * where the callback hook reads the marker and reloads the list.
   */
  const handleLink = (provider: string) => {
    const identity = getIdentityClient();
    if (identity === null) {
      setError('Connected accounts are not available in this deployment.');
      return;
    }
    setBusy(true);
    void identity.linkOAuthProvider(provider, {
      returnTo: `${globalThis.location.pathname}${globalThis.location.search}`,
    });
  };

  const handleUnlink = async (link: OAuthLink) => {
    const label =
      providers.find((p) => p.id === link.provider)?.displayName ??
      link.provider;
    if (!window.confirm(`Disconnect your ${label} account?`)) return;
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const result = await unlinkProvider(link.provider);
      if (result.status === 'ok') {
        setSuccess(`${label} disconnected.`);
        await load();
      } else {
        setError(result.error);
      }
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  const linkable = providers.filter(
    (provider) => !links.some((link) => link.provider === provider.id)
  );

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-white">Connected accounts</h3>
        <p className="text-sm text-muted-foreground">
          Sign in to CarModPicker with an account you already have.
        </p>
      </div>

      {error && <ErrorAlert message={error} />}
      {success && <ConfirmationAlert message={success} />}

      {providers.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No sign in providers are configured for this deployment.
        </p>
      )}

      {links.length > 0 && (
        <ul className="space-y-2">
          {links.map((link) => {
            const label =
              providers.find((p) => p.id === link.provider)?.displayName ??
              link.provider;
            return (
              <li
                key={link.provider}
                className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/5 p-3"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span className="shrink-0 text-primary">
                    <ProviderIcon provider={link.provider} />
                  </span>
                  <div className="min-w-0">
                    <div className="truncate font-medium text-white">
                      {label}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {link.email || 'Connected'} · since{' '}
                      {formatDate(link.linkedAt)}
                    </div>
                  </div>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="destructive"
                  aria-label={`Disconnect ${label}`}
                  onClick={() => void handleUnlink(link)}
                  disabled={busy}
                >
                  <FaTrash />
                </Button>
              </li>
            );
          })}
        </ul>
      )}

      {linkable.length > 0 && (
        <div className="space-y-2">
          {linkable.map((provider) => (
            <Button
              key={provider.id}
              type="button"
              variant="secondary"
              className="w-full"
              onClick={() => handleLink(provider.id)}
              disabled={busy}
            >
              <ProviderIcon provider={provider.id} />
              <span>Connect {provider.displayName}</span>
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

export default IdentityConnectedAccounts;
