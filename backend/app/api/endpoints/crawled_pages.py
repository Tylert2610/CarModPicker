"""Parses a product page that the browser extension scraped for the caller."""

import hashlib
import logging
from typing import Any, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.api.dependencies.auth import get_current_user
from app.api.services.page_html_sanitizer import sanitize_html
from app.api.services.page_parser import parse_page
from app.core.category_inference import infer_category
from app.core.config import settings
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)
router = APIRouter()

_SCRAPE_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {
        "description": "HTML payload exceeds the configured maximum UTF-8 byte size.",
        "content": {"application/json": {"schema": {"type": "object", "properties": {"detail": {"type": "string"}}}}},
    }
}

_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "gclsrc",
        "dclid",
        "msclkid",
        "twclid",
        "ref",
        "source",
    }
)


def canonicalize_url(url: str) -> str:
    """Normalise a product URL so the same page yields one key, dropping tracking params."""
    try:
        parsed = urlparse(url)
    except Exception:
        return url

    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").lower()
    path = parsed.path
    if path == "/":
        path = ""

    qs_filtered = {
        k: v for k, v in parse_qs(parsed.query, keep_blank_values=True).items() if k.lower() not in _TRACKING_PARAMS
    }
    query = urlencode(qs_filtered, doseq=True)

    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def _html_fingerprint(html: str) -> tuple[int, str]:
    """Return the UTF-8 byte length and SHA-256 of the HTML."""
    b = html.encode("utf-8", errors="replace")
    return len(b), hashlib.sha256(b).hexdigest()


def _enforce_max_html_size(
    html_size_bytes: int,
    *,
    user_id: UUID,
    url: str,
    content_length: Optional[str],
) -> None:
    """Raise 413 when the submitted HTML exceeds the configured size ceiling."""
    max_b = settings.CRAWLED_PAGE_MAX_HTML_BYTES
    if html_size_bytes <= max_b:
        return
    logger.warning(
        "Scraped page HTML rejected over max size user_id=%s url=%s html_bytes=%s max_bytes=%s content_length=%s",
        user_id,
        url,
        html_size_bytes,
        max_b,
        content_length,
    )
    raise HTTPException(
        status_code=413,
        detail=(
            f"HTML payload exceeds maximum size ({max_b} UTF-8 bytes); "
            f"submitted html is {html_size_bytes} bytes. "
            "Increase CRAWLED_PAGE_MAX_HTML_BYTES if this limit is too strict."
        ),
    )


class ScrapeRequest(BaseModel):
    """A product page URL and its HTML, submitted by the browser extension."""

    url: str
    html: str


class ScrapeResponse(BaseModel):
    """The part fields parsed out of a scraped product page."""

    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    image_urls: List[str] = []
    product_url: str
    part_manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    adapter_used: str
    inferred_category: Optional[str] = None
    html_size_bytes: int = 0
    html_sha256: str = ""


@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    status_code=status.HTTP_200_OK,
    responses=_SCRAPE_RESPONSES,
)
async def scrape_page_from_extension(
    request: Request,
    body: ScrapeRequest,
    current_user: DBUser = Depends(get_current_user),
) -> ScrapeResponse:
    """Parse a scraped product page into part fields the caller can review."""
    raw_url = body.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="url is required")
    if not body.html:
        raise HTTPException(status_code=400, detail="html is required")

    url = canonicalize_url(raw_url)
    raw_size_bytes, _ = _html_fingerprint(body.html)
    _enforce_max_html_size(
        raw_size_bytes,
        user_id=current_user.id,
        url=url,
        content_length=request.headers.get("content-length"),
    )

    sanitized_html = sanitize_html(body.html)
    html_size_bytes, html_sha256 = _html_fingerprint(sanitized_html)

    try:
        payload = parse_page(sanitized_html, url)
    except Exception as exc:
        logger.warning("Generic parser failed on %s: %s", url, exc)
        payload = None

    if payload is None:
        logger.info("Generic parser returned None for %s, returning empty ScrapeResponse", url)
        return ScrapeResponse(
            product_url=url,
            adapter_used="generic",
            html_size_bytes=html_size_bytes,
            html_sha256=html_sha256,
        )

    inferred = infer_category(payload.name, payload.description)

    return ScrapeResponse(
        name=payload.name,
        description=payload.description,
        price=payload.price_cents,
        image_urls=payload.image_urls or [],
        product_url=payload.product_url,
        part_manufacturer=payload.part_manufacturer,
        part_number=payload.part_number,
        adapter_used="generic",
        inferred_category=inferred,
        html_size_bytes=html_size_bytes,
        html_sha256=html_sha256,
    )
