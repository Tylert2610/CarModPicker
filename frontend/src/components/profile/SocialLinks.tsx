import React from 'react';
import type { IconType } from 'react-icons';
import {
  SiFacebook,
  SiInstagram,
  SiReddit,
  SiTiktok,
  SiYoutube,
} from 'react-icons/si';

/** A user's social profile URLs; only non-empty entries are rendered. */
export interface SocialLinksData {
  instagram_url?: string | null;
  facebook_url?: string | null;
  reddit_url?: string | null;
  youtube_url?: string | null;
  tiktok_url?: string | null;
}

interface SocialLinksProps {
  /** User's social URLs; only non-empty values are shown */
  links: SocialLinksData;
  /** Optional class for the container */
  className?: string;
  /** Icon size in pixels (default 18) */
  iconSize?: number;
}

const PLATFORMS: Array<{
  key: keyof SocialLinksData;
  label: string;
  ariaLabel: string;
  Icon: IconType;
}> = [
  {
    key: 'instagram_url',
    label: 'Instagram',
    ariaLabel: 'Instagram profile',
    Icon: SiInstagram,
  },
  {
    key: 'facebook_url',
    label: 'Facebook',
    ariaLabel: 'Facebook profile',
    Icon: SiFacebook,
  },
  {
    key: 'reddit_url',
    label: 'Reddit',
    ariaLabel: 'Reddit profile',
    Icon: SiReddit,
  },
  {
    key: 'youtube_url',
    label: 'YouTube',
    ariaLabel: 'YouTube channel',
    Icon: SiYoutube,
  },
  {
    key: 'tiktok_url',
    label: 'TikTok',
    ariaLabel: 'TikTok profile',
    Icon: SiTiktok,
  },
];

/**
 * Renders a user's non-empty social profile links with platform logos,
 * opening each in a new tab with rel="noopener noreferrer".
 */
const SocialLinks: React.FC<SocialLinksProps> = ({
  links,
  className = '',
  iconSize = 18,
}) => {
  const entries = PLATFORMS.filter((p) => {
    const v = links[p.key];
    return typeof v === 'string' && v.trim() !== '';
  });

  if (entries.length === 0) {
    return null;
  }

  return (
    <div className={className}>
      <p className="text-sm font-medium text-gray-400 mb-2">Social links</p>
      <ul className="flex flex-wrap gap-2" role="list">
        {entries.map(({ key, label, ariaLabel, Icon }) => {
          const href = links[key] as string;
          return (
            <li key={key}>
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-700/50 text-gray-300 hover:bg-info/30 hover:text-info transition-colors text-sm"
                aria-label={ariaLabel}
              >
                <Icon size={iconSize} className="shrink-0" aria-hidden />
                <span>{label}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default SocialLinks;
