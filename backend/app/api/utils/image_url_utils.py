"""
Utilities for normalizing image URLs to support deduplication across size variants.
Common CDN patterns: Shopify (width=, height=), imgix (w=, h=), Cloudinary, etc.
"""

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

SIZE_PARAMS = frozenset({"width", "height", "w", "h", "size", "resize", "dpr", "q", "quality", "format", "fit", "crop"})

PREFERRED_WIDTH = 5760


def get_canonical_image_url(url: str) -> str:
    """
    Normalize an image URL to a canonical form for deduplication.
    Strips size-related query params so that ...&width=416 and ...&width=3000
    map to the same canonical URL.
    """
    if not url or not url.strip():
        return ""
    try:
        parsed = urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return url
        scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme
        netloc = parsed.netloc.lower().lstrip("www.")
        params = parse_qs(parsed.query, keep_blank_values=False)
        filtered = {k: v for k, v in params.items() if k.lower() not in SIZE_PARAMS}
        new_query = urlencode(filtered, doseq=True)
        return urlunparse((scheme, netloc, parsed.path or "/", parsed.params, new_query, ""))
    except Exception:
        return url


def get_high_res_image_url(url: str) -> str:
    """
    Transform an image URL to request high resolution.
    Adds or replaces width param with a high value (e.g. Shopify supports 5760).
    Use this when fetching to store the best quality.
    """
    if not url or not url.strip():
        return url
    try:
        parsed = urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return url
        scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme
        netloc = parsed.netloc.lower()
        params = parse_qs(parsed.query, keep_blank_values=True)
        params = {k: v for k, v in params.items() if k.lower() not in SIZE_PARAMS}
        params["width"] = [str(PREFERRED_WIDTH)]
        new_query = urlencode(params, doseq=True)
        return urlunparse((scheme, netloc, parsed.path or "/", parsed.params, new_query, ""))
    except Exception:
        return url
