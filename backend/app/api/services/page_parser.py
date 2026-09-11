"""Generic page-parsing helpers for the Chrome extension's `POST /crawled-pages/scrape`

flow. Extracts product details from a fetched HTML payload using JSON-LD Product
schema first, then OpenGraph / DOM fallbacks for price and image. No retailer-
"""

from __future__ import annotations

import html as html_module
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag


@dataclass
class ParsedPage:
    """Canonical output from generic page parsing."""

    name: str
    product_url: str
    description: Optional[str] = None
    price_cents: Optional[int] = None
    part_manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    image_urls: Optional[List[str]] = None


_PART_NUMBER_PREFIXES = (
    r"^SKU\s*:\s*",
    r"^Part\s*#\s*:\s*",
    r"^Part\s*Number\s*:\s*",
    r"^Item\s*#\s*:\s*",
    r"^Product\s*Code\s*:\s*",
    r"^Model\s*#?\s*:\s*",
    r"^Code\s*:\s*",
)

_PART_NUMBER_CAR_MODEL_BLACKLIST = frozenset(
    {
        "z4m",
        "1m",
        "e8x",
        "e9x",
        "e46",
        "e90",
        "e92",
        "e82",
        "e85",
        "e86",
        "f80",
        "f82",
        "f10",
        "f12",
        "e60",
        "e63",
        "e64",
    }
)


def parse_price_cents(text: str) -> Optional[int]:
    """Extract first price in cents from a text snippet (e.g. ``"From $2,642.46"``)."""
    if not text or not text.strip():
        return None
    cleaned = re.sub(r"[$,\s]", "", text)
    match = re.search(r"(\d+\.?\d*)", cleaned)
    if not match:
        return None
    try:
        dollars = float(match.group(1))
    except ValueError:
        return None
    if dollars < 0:
        return None
    return int(round(dollars * 100))


def normalize_description_text(raw: Optional[str], max_len: int = 2000) -> Optional[str]:
    """Decode entities, strip HTML, collapse whitespace, cap length."""
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    if "<" in s and ">" in s:
        s = BeautifulSoup(s, "html.parser").get_text(separator=" ", strip=True)
    else:
        s = html_module.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len] if s else None


def normalize_part_number(raw: Optional[str]) -> Optional[str]:
    """Strip prefixes (``SKU:``, ``Part #:``, etc.) and reject car/model codes."""
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    for pattern in _PART_NUMBER_PREFIXES:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    s = s.strip()
    if not s:
        return None
    key = re.sub(r"\s+", "", s).lower()
    if key in _PART_NUMBER_CAR_MODEL_BLACKLIST:
        return None
    return s


def part_number_canonical(raw: Optional[str]) -> Optional[str]:
    """
    Canonical dedup key: strip prefixes, drop non-alphanumerics, uppercase.
    Returns None for empty input, results shorter than 4 chars, or blacklist hits.
    """
    normalized = normalize_part_number(raw)
    if not normalized:
        return None
    canonical = re.sub(r"[^A-Za-z0-9]", "", normalized).upper()
    if not canonical or len(canonical) < 4:
        return None
    if canonical.lower() in _PART_NUMBER_CAR_MODEL_BLACKLIST:
        return None
    return canonical


def _meta_content(tag: Optional[Tag]) -> Optional[str]:
    """Return a meta tag's content attribute when it is a string."""
    if not isinstance(tag, Tag):
        return None
    content = tag.get("content")
    return content if isinstance(content, str) else None


def _canonical_url_key(url: Optional[str]) -> Optional[str]:
    """Normalize a URL for equality (collapse http/https, lowercase host, strip trailing slash, drop query)."""
    if not url or not isinstance(url, str):
        return None
    s = url.strip()
    if not s:
        return None
    try:
        parsed = urlparse(s)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    scheme = parsed.scheme.lower()
    if scheme in ("http", "https"):
        scheme = "http"
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return f"{scheme}://{parsed.netloc.lower()}{path}"


def _json_ld_product_urls(item: Dict[str, Any]) -> List[str]:
    """Collect every candidate product URL from a JSON-LD item."""
    urls: List[str] = []

    def _append(val: Any) -> None:
        """Append a URL, recursing through lists and objects."""
        if isinstance(val, str) and val.strip():
            urls.append(val.strip())
        elif isinstance(val, list):
            for v in val:
                _append(v)
        elif isinstance(val, dict):
            _append(val.get("url") or val.get("@id"))

    _append(item.get("url"))
    _append(item.get("@id"))
    _append(item.get("sameAs"))
    offers = item.get("offers") or item.get("Offers")
    if isinstance(offers, dict):
        _append(offers.get("url"))
    elif isinstance(offers, list):
        for off in offers:
            if isinstance(off, dict):
                _append(off.get("url"))
    return urls


def _escape_json_control_chars(raw: str) -> str:
    """Escape raw control chars inside JSON string values (some Shopify themes emit unescaped newlines)."""
    out: List[str] = []
    in_str = False
    esc = False
    for ch in raw:
        cp = ord(ch)
        if in_str:
            if esc:
                esc = False
                out.append(ch)
                continue
            if ch == "\\":
                esc = True
                out.append(ch)
                continue
            if ch == '"':
                in_str = False
                out.append(ch)
                continue
            if cp <= 0x1F:
                out.append(f"\\u{cp:04x}")
                continue
            out.append(ch)
            continue
        if ch == '"':
            in_str = True
        out.append(ch)
    return "".join(out)


def _json_ld_type_is_product(t: Any) -> bool:
    """Report whether a JSON-LD @type denotes a Product."""
    if isinstance(t, str):
        return t.strip().lower() == "product"
    if isinstance(t, list):
        return any(isinstance(x, str) and x.strip().lower() == "product" for x in t)
    return False


def _extract_json_ld_product(html: str, *, product_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Find the JSON-LD Product block matching ``product_url`` (or first Product if no URL)."""
    want_key = _canonical_url_key(product_url)
    soup = BeautifulSoup(html, "html.parser")
    fallback_no_url: Optional[Dict[str, Any]] = None
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                data = json.loads(_escape_json_control_chars(raw))
            except json.JSONDecodeError:
                continue
        items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            items = cast(List[Dict[str, Any]], data)
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items = cast(List[Dict[str, Any]], data["@graph"])
            else:
                items = [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if not _json_ld_type_is_product(item.get("@type")):
                continue
            if want_key is None:
                return item
            declared = [k for k in (_canonical_url_key(u) for u in _json_ld_product_urls(item)) if k]
            if any(k == want_key for k in declared):
                return item
            if not declared and fallback_no_url is None:
                fallback_no_url = item
    return fallback_no_url


def _part_manufacturer_from_json_ld(item: Dict[str, Any]) -> Optional[str]:
    """Return the brand name from a JSON-LD item."""
    brand = item.get("brand")
    if isinstance(brand, str) and brand.strip():
        return html_module.unescape(brand.strip())
    if isinstance(brand, dict):
        name = brand.get("name")
        if isinstance(name, str) and name.strip():
            return html_module.unescape(name.strip())
    return None


def _price_from_json_ld(item: Dict[str, Any]) -> Optional[int]:
    """Return the offer price in cents from a JSON-LD item."""
    offers = item.get("offers")
    offer: Optional[Dict[str, Any]]
    if isinstance(offers, list) and offers:
        offer = cast(Dict[str, Any], offers[0])
    elif isinstance(offers, dict):
        offer = offers
    else:
        offer = None
    if not isinstance(offer, dict):
        return None
    for key in ("price", "lowPrice", "highPrice"):
        val = offer.get(key)
        if val is None:
            continue
        try:
            num = float(str(val).replace(",", ""))
        except (ValueError, TypeError):
            continue
        if num <= 0:
            continue
        return int(round(num * 100))
    return None


def _images_from_json_ld(item: Dict[str, Any]) -> List[str]:
    """Return the image URLs from a JSON-LD item."""
    img = item.get("image")
    if not img:
        return []
    if isinstance(img, str):
        candidates: List[Any] = [img]
    elif isinstance(img, dict):
        candidates = [img]
    elif isinstance(img, list):
        candidates = img
    else:
        return []
    urls: List[str] = []
    for i in candidates:
        if isinstance(i, str) and i.strip():
            urls.append(i.strip())
        elif isinstance(i, dict):
            for key in ("url", "contentUrl", "image"):
                v = i.get(key)
                if isinstance(v, str) and v.strip():
                    urls.append(v.strip())
                    break
    return urls


def _extract_dom_price(soup: BeautifulSoup) -> Optional[int]:
    """OpenGraph price meta first, then first ``$NN.NN`` in body text."""
    for prop in ("product:price:amount", "og:price:amount"):
        meta = soup.find("meta", property=prop)
        if isinstance(meta, Tag):
            content = _meta_content(meta)
            if content:
                cents = parse_price_cents(content)
                if cents is not None:
                    return cents
    body = soup.get_text()
    match = re.search(r"(?:From\s*)?\$[\s,]?\d+\.?\d*", body)
    if match:
        return parse_price_cents(match.group(0))
    return None


def _og_meta(soup: BeautifulSoup, prop: str) -> Optional[str]:
    """Return the content of an OpenGraph meta property."""
    return _meta_content(soup.find("meta", property=prop))


def parse_page(html: str, product_url: str) -> Optional[ParsedPage]:
    """
    Generic product-page parser. Tries JSON-LD Product first; falls back to
    OpenGraph + ``<title>`` + DOM price. Returns ``None`` when no usable name.
    """
    item = _extract_json_ld_product(html, product_url=product_url)
    if item is not None:
        name_val = item.get("name")
        name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
        if name:
            name = html_module.unescape(name)
            desc_val = item.get("description")
            description: Optional[str] = None
            if isinstance(desc_val, str) and len(desc_val.strip()) > 10:
                description = normalize_description_text(desc_val, max_len=2000)
            sku_val = item.get("sku") or item.get("mpn")
            part_number = normalize_part_number(sku_val) if isinstance(sku_val, str) else None
            images = _images_from_json_ld(item)
            return ParsedPage(
                name=name,
                product_url=product_url,
                description=description,
                price_cents=_price_from_json_ld(item),
                part_manufacturer=_part_manufacturer_from_json_ld(item),
                part_number=part_number,
                image_urls=images[:12] if images else None,
            )

    soup = BeautifulSoup(html, "html.parser")
    name = _og_meta(soup, "og:title")
    if not name:
        title_tag = soup.find("title")
        if isinstance(title_tag, Tag):
            text = title_tag.get_text(strip=True)
            name = text or None
    if not name:
        return None
    name = html_module.unescape(name).strip()
    description = normalize_description_text(_og_meta(soup, "og:description"), max_len=2000)
    image_url = _og_meta(soup, "og:image")
    return ParsedPage(
        name=name,
        product_url=product_url,
        description=description,
        price_cents=_extract_dom_price(soup),
        part_manufacturer=None,
        part_number=None,
        image_urls=[image_url] if image_url else None,
    )
