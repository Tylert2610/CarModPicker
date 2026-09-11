"""Dynamic XML sitemap generation for Google Search Console.

The frontend is a static SPA on S3/CloudFront and cannot generate a sitemap
from the database, so the backend produces one here. A sitemap *index* is
"""

from __future__ import annotations

from datetime import datetime
from html import escape as _html_escape

from app.api.dependencies.repositories import get_repositories
from app.core.config import settings
from app.db.dynamo.models import TimestampedDynamoModel

URLS_PER_PAGE = 20_000

SITEMAP_STATIC = "static"
SITEMAP_PARTS = "parts"
SITEMAP_CARS = "cars"
SITEMAP_BUILD_LISTS = "build-lists"

_STATIC_PAGES: list[tuple[str, str, str]] = [
    ("/", "daily", "1.0"),
    ("/build-lists", "daily", "0.9"),
    ("/search", "weekly", "0.7"),
    ("/about", "monthly", "0.6"),
    ("/pricing", "monthly", "0.6"),
    ("/support", "monthly", "0.5"),
    ("/contact-us", "monthly", "0.4"),
    ("/privacy-policy", "yearly", "0.3"),
    ("/terms-of-service", "yearly", "0.3"),
]


def _base_url() -> str:
    """SPA origin without trailing slash, e.g. https://www.carmodpicker.com."""
    return settings.frontend_base_url.rstrip("/")


def _api_base_url() -> str:
    """Origin the sitemap files themselves are served from (this backend).

    The index must reference child sitemaps by absolute URL, and they live on
    the API host, not the SPA host."""
    return settings.api_base_url.rstrip("/")


def escape(text: str) -> str:
    """Escape a string for safe inclusion in XML text/attribute content.

    Uses ``html.escape`` (escapes & < > " ') purely for *output* — this
    module never parses XML, so the XML-parsing attack class does not apply
    """
    return _html_escape(text, quote=True)


def _w3c_datetime(dt: datetime) -> str:
    """Format a datetime as a W3C/ISO-8601 string for <lastmod>."""
    return dt.replace(microsecond=0).isoformat()


def _url_element(
    loc: str,
    *,
    lastmod: datetime | None = None,
    changefreq: str | None = None,
    priority: str | None = None,
) -> str:
    """Render one <url> entry for a sitemap."""
    parts = [f"  <url>\n    <loc>{escape(loc)}</loc>"]
    if lastmod is not None:
        parts.append(f"    <lastmod>{_w3c_datetime(lastmod)}</lastmod>")
    if changefreq is not None:
        parts.append(f"    <changefreq>{changefreq}</changefreq>")
    if priority is not None:
        parts.append(f"    <priority>{priority}</priority>")
    parts.append("  </url>")
    return "\n".join(parts)


def _urlset(url_elements: list[str]) -> str:
    """Wrap rendered <url> entries in a sitemap urlset document."""
    body = "\n".join(url_elements)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def _canonical_parts() -> list[TimestampedDynamoModel]:
    """Return every canonical part row."""
    return list(get_repositories().parts.list_canonical())


def _build_lists() -> list[TimestampedDynamoModel]:
    """Return every build list row."""
    return list(get_repositories().build_lists.scan_all())


def _car_generations() -> list[TimestampedDynamoModel]:
    """Return every car generation row."""
    return list(get_repositories().car_generations.list_all())


def page_count(total: int) -> int:
    """Number of sitemap pages for a total row count (>=1 so an empty type
    still yields one valid, empty child sitemap)."""
    if total <= 0:
        return 1
    return (total + URLS_PER_PAGE - 1) // URLS_PER_PAGE


def generate_sitemap_index() -> str:
    """Sitemap index referencing every child sitemap page."""
    api = _api_base_url()
    now = _w3c_datetime(datetime.now().astimezone())

    sitemaps: list[str] = []

    def add(name: str, pages: int) -> None:
        """Append the child sitemap entries for one type."""
        for page in range(1, pages + 1):
            suffix = "" if page == 1 else f"?page={page}"
            loc = f"{api}/sitemap-{name}.xml{suffix}"
            sitemaps.append(
                "  <sitemap>\n" f"    <loc>{escape(loc)}</loc>\n" f"    <lastmod>{now}</lastmod>\n" "  </sitemap>"
            )

    add(SITEMAP_STATIC, 1)
    add(SITEMAP_PARTS, page_count(len(_canonical_parts())))
    add(SITEMAP_CARS, page_count(len(_car_generations())))
    add(SITEMAP_BUILD_LISTS, page_count(len(_build_lists())))

    body = "\n".join(sitemaps)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</sitemapindex>\n"
    )


def generate_static_sitemap() -> str:
    """Render the sitemap covering the static marketing pages."""
    base = _base_url()
    elements = [
        _url_element(f"{base}{path}", changefreq=changefreq, priority=priority)
        for path, changefreq, priority in _STATIC_PAGES
    ]
    return _urlset(elements)


def _dynamo_sitemap(
    rows: list[TimestampedDynamoModel],
    url_prefix: str,
    page: int,
    *,
    changefreq: str,
    priority: str,
) -> str:
    """Render one page of a sitemap from stored rows, ordered by id."""
    base = _base_url()
    offset = (page - 1) * URLS_PER_PAGE
    ordered = sorted(rows, key=lambda row: str(row.id))[offset : offset + URLS_PER_PAGE]
    elements = [
        _url_element(
            f"{base}{url_prefix}/{row.id}",
            lastmod=row.updated_at,
            changefreq=changefreq,
            priority=priority,
        )
        for row in ordered
    ]
    return _urlset(elements)


def generate_child_sitemap(name: str, page: int) -> str | None:
    """Render child sitemap ``name`` page ``page`` (1-based).

    Returns None for an unknown name so the route can 404."""
    if page < 1:
        page = 1
    if name == SITEMAP_STATIC:
        return generate_static_sitemap()
    if name == SITEMAP_PARTS:
        return _dynamo_sitemap(_canonical_parts(), "/parts", page, changefreq="weekly", priority="0.7")
    if name == SITEMAP_CARS:
        return _dynamo_sitemap(_car_generations(), "/car-generations", page, changefreq="monthly", priority="0.6")
    if name == SITEMAP_BUILD_LISTS:
        return _dynamo_sitemap(_build_lists(), "/build-lists", page, changefreq="weekly", priority="0.6")
    return None
