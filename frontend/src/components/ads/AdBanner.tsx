import { useEffect, useRef, useState } from 'react';

import { useCookieConsent } from '../../hooks/useCookieConsent';
import { ADSENSE_CLIENT_ID } from './adsenseConfig';

const AD_WIDTH = 160;
const AD_HEIGHT = 600;
const AD_GAP = 48;
const PADDING_Y = 48;
const OUTER_EDGE_MARGIN = 20;
const MARGIN = 8;

type AdBannerSide = 'left' | 'right';

interface AdBannerProps {
  side: AdBannerSide;
  slotId?: string | undefined;
}

declare global {
  interface Window {
    adsbygoogle: unknown[];
  }
}

/** One AdSense unit in the stack, pushed to adsbygoogle once consent allows. */
function SingleAd({
  canServeAds,
  slotId,
  clientId,
  index,
}: {
  canServeAds: boolean;
  slotId?: string | undefined;
  clientId?: string | undefined;
  index: number;
}) {
  const insRef = useRef<HTMLModElement>(null);

  useEffect(() => {
    if (!canServeAds || !slotId || !insRef.current) return;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
      // eslint-disable-next-line no-empty
    } catch {}
  }, [canServeAds, slotId]);

  return (
    <div
      className="rounded-lg overflow-hidden border border-white/10 bg-black/20 flex items-center justify-center flex-shrink-0"
      style={{
        width: AD_WIDTH,
        height: AD_HEIGHT,
        marginLeft: MARGIN,
        marginRight: MARGIN,
      }}
    >
      {canServeAds && slotId ? (
        <ins
          ref={insRef}
          className="adsbygoogle"
          style={{ display: 'block', height: AD_HEIGHT, width: AD_WIDTH }}
          data-ad-client={clientId}
          data-ad-slot={slotId}
          data-ad-format="auto"
          data-full-width-responsive="false"
        />
      ) : (
        <div
          className="text-muted-foreground text-xs text-center p-4 flex flex-col items-center justify-center"
          style={{ height: AD_HEIGHT, width: AD_WIDTH }}
        >
          <span>Ad {index + 1}</span>
        </div>
      )}
    </div>
  );
}

/**
 * Global sidebar ad banner. Stacks as many ads as fit in the available column height.
 * The aside uses self-stretch so its height is driven by the sibling content div,
 * making it safe to ResizeObserver the aside itself without feedback loops.
 */
export default function AdBanner({ side, slotId }: AdBannerProps) {
  const asideRef = useRef<HTMLElement>(null);
  const [adCount, setAdCount] = useState(1);

  const clientId = ADSENSE_CLIENT_ID;
  const { consent } = useCookieConsent();
  const canServeAds = consent === 'accepted';

  useEffect(() => {
    const el = asideRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      const available = el.offsetHeight - 2 * PADDING_Y;
      const count = Math.max(
        1,
        Math.floor((available + AD_GAP) / (AD_HEIGHT + AD_GAP))
      );
      setAdCount(count);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <aside
      ref={asideRef}
      className="hidden lg:flex self-stretch flex-shrink-0 flex-col items-center justify-start"
      style={{
        width: AD_WIDTH,
        gap: AD_GAP,
        paddingTop: PADDING_Y,
        paddingBottom: PADDING_Y,
        ...(side === 'left'
          ? { marginLeft: OUTER_EDGE_MARGIN }
          : { marginRight: OUTER_EDGE_MARGIN }),
      }}
      aria-label={`Advertisement ${side}`}
    >
      {Array.from({ length: adCount }, (_, i) => (
        <SingleAd
          key={i}
          index={i}
          canServeAds={canServeAds}
          slotId={slotId}
          clientId={clientId}
        />
      ))}
    </aside>
  );
}
