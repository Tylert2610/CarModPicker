/**
 * The "Continue with X" buttons on the login page, in identity mode.
 *
 * The set comes from `GET /api/auth/oauth/providers` rather than from a
 * hardcoded list, so a deployment that configures GitHub gets a GitHub button
 * with no frontend change and one that configures nothing renders nothing. See
 * `../../api/oauthProviders` for why that is a read rather than a probe.
 *
 * ## Why these are anchors and not buttons
 *
 * The start route answers a `302` to the provider, whose host sends no CORS
 * headers, so it has to be a real navigation rather than a `fetch`. Rendering
 * the URL on an anchor is the simplest way to get that, and it also gets
 * middle-click and "open in new tab" behaving the way a user expects.
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
