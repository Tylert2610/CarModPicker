"""Sanitize HTML submitted by the Chrome extension before archival or parsing.

The extension transmits a full DOM snapshot of whatever page the user scrapes, so
the payload can incidentally include autofilled form values, personalized widgets,
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

_META_ALLOWED_PROPERTY_PREFIXES = ("og:", "twitter:", "product:")
_META_ALLOWED_NAMES = frozenset(
    {
        "description",
        "keywords",
        "viewport",
        "robots",
        "twitter:card",
        "twitter:title",
        "twitter:description",
        "twitter:image",
    }
)
_META_ALLOWED_HTTP_EQUIV = frozenset({"content-type", "content-language"})

_STRIP_ATTR_TAGS = frozenset({"input", "textarea", "select", "option", "button"})
_FORM_VALUE_ATTRS = ("value", "checked", "selected", "placeholder")


def sanitize_html(html: str) -> str:
    """Return ``html`` with PII-risk content removed, preserving product markup."""
    soup = BeautifulSoup(html, "html.parser")

    for style in soup.find_all("style"):
        style.decompose()
    for tag_name in ("noscript", "iframe", "object", "embed"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for script in soup.find_all("script"):
        if not isinstance(script, Tag):
            continue
        script_type = script.get("type")
        if isinstance(script_type, str) and script_type.strip().lower() == "application/ld+json":
            continue
        script.decompose()

    for meta in list(soup.find_all("meta")):
        if not isinstance(meta, Tag):
            continue
        if not _is_meta_allowed(meta):
            meta.decompose()

    for tag in soup.find_all(_STRIP_ATTR_TAGS):
        if not isinstance(tag, Tag):
            continue
        for attr in _FORM_VALUE_ATTRS:
            if attr in tag.attrs:
                del tag.attrs[attr]
        if tag.name == "textarea":
            tag.clear()

    return str(soup)


def _is_meta_allowed(meta: Tag) -> bool:
    """Report whether a meta tag is on the sanitizer allow list."""
    if meta.has_attr("charset"):
        return True
    prop = meta.get("property")
    if isinstance(prop, str):
        prop_lower = prop.strip().lower()
        if any(prop_lower.startswith(prefix) for prefix in _META_ALLOWED_PROPERTY_PREFIXES):
            return True
    name = meta.get("name")
    if isinstance(name, str) and name.strip().lower() in _META_ALLOWED_NAMES:
        return True
    http_equiv = meta.get("http-equiv")
    if isinstance(http_equiv, str) and http_equiv.strip().lower() in _META_ALLOWED_HTTP_EQUIV:
        return True
    if meta.has_attr("itemprop"):
        return True
    return False
