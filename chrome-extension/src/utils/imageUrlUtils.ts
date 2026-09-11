/**
 * Normalize image URLs across CDN size variants (Shopify, imgix and similar) so
 * the same image dedupes to one entry.
 */

const SIZE_PARAMS = new Set([
  "width",
  "height",
  "w",
  "h",
  "size",
  "resize",
  "dpr",
  "q",
  "quality",
  "format",
  "fit",
  "crop",
]);

const PREFERRED_WIDTH = 5760;

/** Strip size params so every variant of an image shares one canonical URL. */
export function getCanonicalImageUrl(url: string): string {
  if (!url?.trim()) return "";
  try {
    const u = new URL(url.trim());
    const params = new URLSearchParams(u.search);
    for (const key of Array.from(params.keys())) {
      if (SIZE_PARAMS.has(key.toLowerCase())) {
        params.delete(key);
      }
    }
    const newSearch = params.toString();
    u.search = newSearch;
    u.protocol = "https:";
    u.hostname = u.hostname.toLowerCase().replace(/^www\./, "");
    return u.toString();
  } catch {
    return url;
  }
}

/** Request the highest resolution variant, for fetching an image to store. */
export function getHighResImageUrl(url: string): string {
  if (!url?.trim()) return url;
  try {
    const u = new URL(url.trim());
    const params = new URLSearchParams(u.search);
    for (const key of Array.from(params.keys())) {
      if (SIZE_PARAMS.has(key.toLowerCase())) {
        params.delete(key);
      }
    }
    params.set("width", String(PREFERRED_WIDTH));
    u.search = params.toString();
    u.protocol = "https:";
    return u.toString();
  } catch {
    return url;
  }
}
