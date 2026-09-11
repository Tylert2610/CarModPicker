/**
 * Builds display URLs for externally hosted images, requesting a smaller
 * variant where the host supports URL-based transforms so a thumbnail does not
 * decode a full resolution original.
 */

export type ExternalImageVariant = 'thumbnail' | 'hero' | 'carouselTile';

/** Max edge for hero `fit` — ~2× typical max layout width, good quality without 8K decode */
const HERO_FIT_MAX = 1680;

/** Square fill for small thumbnails (2× retina for ~96px tiles) */
const THUMB_FILL = 256;

/** Carousel strip tiles are ~160px; 2× retina */
const CAROUSEL_TILE_FILL = 360;

function isWixStaticHost(hostname: string): boolean {
  return hostname.toLowerCase() === 'static.wixstatic.com';
}

function isShopifyCdnHost(hostname: string): boolean {
  return (
    /\.shopify\.com$/i.test(hostname) ||
    hostname.toLowerCase() === 'cdn.shopify.com'
  );
}

/**
 * Wix: `https://static.wixstatic.com/media/<id>~mv2.ext/v1/fit/w_640,h_640/file.webp`
 * Output segment is always `file.<ext>` per Wix docs (not the original filename).
 */
function wixTransformedUrl(
  url: string,
  method: 'fit' | 'fill',
  w: number,
  h: number,
  outExt: 'webp' | 'jpg' = 'webp'
): string | null {
  try {
    const u = new URL(url);
    if (!isWixStaticHost(u.hostname)) return null;
    if (!u.pathname.startsWith('/media/')) return null;
    if (/\/v1\/(fit|fill|crop)\//i.test(u.pathname)) return null;

    const base = `${u.origin}${u.pathname}`;
    return `${base}/v1/${method}/w_${w},h_${h}/file.${outExt}`;
  } catch {
    return null;
  }
}

/**
 * Shopify image URLs often accept `width` (and optionally `height`) query params.
 */
function shopifyResizedUrl(url: string, width: number): string | null {
  try {
    const u = new URL(url);
    if (!isShopifyCdnHost(u.hostname)) return null;
    if (u.searchParams.has('width')) return null;
    u.searchParams.set('width', String(width));
    return u.toString();
  } catch {
    return null;
  }
}

/**
 * Returns a URL appropriate for `variant`, or the original URL if no rule applies.
 */
export function buildExternalImageUrl(
  originalUrl: string | null | undefined,
  variant: ExternalImageVariant
): string | null {
  if (originalUrl == null || !String(originalUrl).trim()) return null;
  const url = String(originalUrl).trim();

  let wix: string | null = null;
  if (variant === 'thumbnail') {
    wix = wixTransformedUrl(url, 'fill', THUMB_FILL, THUMB_FILL, 'webp');
  } else if (variant === 'carouselTile') {
    wix = wixTransformedUrl(
      url,
      'fill',
      CAROUSEL_TILE_FILL,
      CAROUSEL_TILE_FILL,
      'webp'
    );
  } else {
    wix = wixTransformedUrl(url, 'fit', HERO_FIT_MAX, HERO_FIT_MAX, 'webp');
  }
  if (wix) return wix;

  const shopifyW =
    variant === 'thumbnail'
      ? THUMB_FILL
      : variant === 'carouselTile'
        ? CAROUSEL_TILE_FILL
        : HERO_FIT_MAX;
  const shopify = shopifyResizedUrl(url, shopifyW);
  if (shopify) return shopify;

  return url;
}
