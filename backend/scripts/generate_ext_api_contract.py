#!/usr/bin/env python3
"""
AUTH-06 + D-34—D-37: Chrome Extension API Contract Generator.

Generates ``chrome-extension/API_CONTRACT.md`` from ``app.openapi()`` for the
16 endpoints the extension calls (allow-list inline below).

Usage:

    # Default — write to chrome-extension/API_CONTRACT.md:
    cd backend
    TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py

    # --stdout — emit Markdown to stdout (used by drift-guard test):
    cd backend
    TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout

The companion drift guard (``backend/tests/test_ext_api_contract_up_to_date.py``)
subprocess-invokes this script with ``--stdout`` and asserts the output matches
the committed .md. This avoids Python-level import of the script
(``backend/scripts`` is not a Python package — no ``__init__.py``, not on
``sys.path``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# <repo>/backend/scripts/generate_ext_api_contract.py -> parents[2] = <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "chrome-extension" / "API_CONTRACT.md"

# D-35: Allow-list of (method, path) tuples — mirrors chrome-extension/src/background.ts.
# Verified inventory per RESEARCH.md Finding 3. Any change to this list requires
# regeneration.
EXTENSION_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/users/me"),
    ("GET", "/api/categories/"),
    ("GET", "/api/retailers"),
    ("POST", "/api/retailers/get-or-create"),
    ("GET", "/api/parts/check-url"),
    ("GET", "/api/parts/{part_id}"),
    ("GET", "/api/parts/find-by-part-manufacturer-and-part-number"),
    ("POST", "/api/parts/{part_id}/append-images"),
    ("POST", "/api/parts"),
    ("POST", "/api/parts/{part_id}/listings"),
    ("GET", "/api/part-manufacturers"),
    ("POST", "/api/part-manufacturers"),
    ("GET", "/api/car-generations"),
    ("GET", "/api/images/by-source-url"),
    ("POST", "/api/images/upload"),
    ("POST", "/api/crawled-pages/scrape"),
]


def resolve_ref(ref: str, schemas: dict[str, Any]) -> dict[str, Any]:
    """Resolve a JSON Schema $ref like ``#/components/schemas/PartRead`` to the schema dict."""
    name = ref.rsplit("/", 1)[-1]
    return schemas.get(name, {})


def flatten_schema(schema: dict[str, Any], schemas: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """Inline ``$ref``-driven references up to depth 3 so the Markdown is human-readable."""
    if depth > 3:
        return schema
    if "$ref" in schema:
        return flatten_schema(resolve_ref(schema["$ref"], schemas), schemas, depth + 1)
    if "properties" in schema:
        return {
            **schema,
            "properties": {k: flatten_schema(v, schemas, depth + 1) for k, v in schema["properties"].items()},
        }
    return schema


def _schema_to_json_block(schema: dict[str, Any]) -> str:
    """Render a schema dict as a fenced JSON code block for readability."""
    return "```json\n" + json.dumps(schema, indent=2, sort_keys=True) + "\n```"


def generate_markdown() -> str:
    """Produce the full API_CONTRACT.md content as a string.

    Called from ``main()`` in both file-write and ``--stdout`` modes. The
    drift-guard test does NOT call this function directly — it invokes this
    script as a subprocess and captures stdout. See docstring at top for
    rationale.
    """
    # Ensure ``backend/`` is on sys.path so ``from app.main import app`` works
    # regardless of cwd. When invoked as ``python scripts/generate_ext_api_contract.py``
    # Python puts ``scripts/`` on sys.path[0], not ``backend/``.
    backend_dir = str(Path(__file__).resolve().parents[1])
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    # Function-scope import — TESTING=true ENABLE_RATE_LIMITING=false must be set
    # BEFORE app.main is imported (conftest-style env-var ordering).
    from app.main import app  # noqa: PLC0415 — intentional ordering

    spec = app.openapi()
    schemas = spec.get("components", {}).get("schemas", {})
    out: list[str] = [
        "# Chrome Extension API Contract",
        "",
        "Generated from `app.openapi()`. Do not edit by hand.",
        "",
        "Regenerate:",
        "",
        "```",
        "cd backend",
        "TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py",
        "```",
        "",
        "---",
        "",
    ]

    for method, path in EXTENSION_ENDPOINTS:
        op = spec.get("paths", {}).get(path, {}).get(method.lower(), {})
        out.append(f"## `{method} {path}`")
        out.append("")
        if op.get("summary"):
            out.append(f"**Summary:** {op['summary']}")
            out.append("")
        if op.get("description"):
            out.append(f"**Description:** {op['description']}")
            out.append("")

        # Parameters (path + query + header)
        params = op.get("parameters", [])
        if params:
            out.append("**Parameters:**")
            out.append("")
            out.append("| Name | In | Required | Schema |")
            out.append("|------|----|----------|--------|")
            for p in params:
                name = p.get("name", "?")
                pin = p.get("in", "?")
                required = "yes" if p.get("required", False) else "no"
                schema = p.get("schema", {})
                # Inline schema type (compact).
                schema_repr = schema.get("type", "") or "$ref"
                if "enum" in schema:
                    schema_repr += f" (enum: {schema['enum']})"
                out.append(f"| `{name}` | {pin} | {required} | {schema_repr} |")
            out.append("")

        # Request body
        req_body = op.get("requestBody")
        if req_body:
            content = req_body.get("content", {}).get("application/json", {})
            schema = content.get("schema", {})
            flat = flatten_schema(schema, schemas)
            out.append("**Request body (`application/json`):**")
            out.append("")
            out.append(_schema_to_json_block(flat))
            out.append("")

        # Responses
        responses = op.get("responses", {})
        if responses:
            out.append("**Responses:**")
            out.append("")
            for status_code in sorted(responses.keys()):
                resp = responses[status_code]
                out.append(f"- `{status_code}` — {resp.get('description', '')}")
                content = resp.get("content", {}).get("application/json", {})
                schema = content.get("schema")
                if schema:
                    flat = flatten_schema(schema, schemas)
                    out.append("")
                    out.append(_schema_to_json_block(flat))
                    out.append("")
            out.append("")

        out.append("---")
        out.append("")

    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Chrome Extension API Contract from app.openapi().",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help=(
            "Emit Markdown to stdout instead of writing "
            "chrome-extension/API_CONTRACT.md. Used by the drift-guard test to "
            "compare against the committed file."
        ),
    )
    args = parser.parse_args()

    md = generate_markdown()

    if args.stdout:
        # Write raw Markdown to stdout; caller (the pytest drift guard) captures it.
        # Do NOT use print() — print appends a newline that would break
        # byte-for-byte equality.
        sys.stdout.write(md)
    else:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(md, encoding="utf-8")
        print(f"Wrote {OUTPUT_PATH} ({len(md)} chars)")


if __name__ == "__main__":
    main()
