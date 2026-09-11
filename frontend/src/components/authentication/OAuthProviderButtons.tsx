/**
 * The "Continue with X" buttons for identity mode, one per provider reported by
 * the providers route. Rendered as anchors because the start route redirects to
 * a host that sends no CORS headers, so it must be a real navigation.
 */
import { useEffect, useState } from 'react';
import { FaGithub, FaGoogle, FaSignInAlt } from 'react-icons/fa';
import { GITHUB_PROVIDER, GOOGLE_PROVIDER } from '@webbpulse/auth';
import { identityUrl } from '../../api/identityClient';
import { oauthStartUrl } from '../../api/identityOAuth';
import {
  OAUTH_PROVIDERS_PATH,
  oauthProviders,
  type OAuthProvider,
} from '../../api/oauthProviders';

/** Props for OAuthProviderButtons: where to land after the callback. */
export interface OAuthProviderButtonsProps {
  /** Where to land after the callback, as a path on this frontend. */
  returnTo?: string;
  disabled?: boolean;
}

/** The provider's mark, where this build has one. */
const ProviderIcon: React.FC<{ provider: string }> = ({ provider }) => {
  if (provider === GOOGLE_PROVIDER) return <FaGoogle />;
  if (provider === GITHUB_PROVIDER) return <FaGithub />;
  return <FaSignInAlt />;
};

function OAuthProviderButtons({
  returnTo,
  disabled,
}: OAuthProviderButtonsProps) {
  const [providers, setProviders] = useState<OAuthProvider[]>([]);

  useEffect(() => {
    let live = true;
    void oauthProviders(identityUrl(OAUTH_PROVIDERS_PATH)).then((list) => {
      if (live) setProviders(list);
    });
    return () => {
      live = false;
    };
  }, []);

  if (providers.length === 0) return null;

  return (
    <div className="space-y-2">
      {providers.map((provider) => {
        const href = oauthStartUrl(provider.id, returnTo);
        if (href === null) return null;
        return (
          <a
            key={provider.id}
            href={disabled ? undefined : href}
            aria-disabled={disabled ? 'true' : undefined}
            className={`inline-flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-md border border-white/10 bg-white/5 px-8 py-3 text-sm font-medium text-white transition-colors hover:bg-white/10 ${
              disabled ? 'pointer-events-none opacity-50' : ''
            }`}
          >
            <ProviderIcon provider={provider.id} />
            <span>Continue with {provider.displayName}</span>
          </a>
        );
      })}
    </div>
  );
}

export default OAuthProviderButtons;
