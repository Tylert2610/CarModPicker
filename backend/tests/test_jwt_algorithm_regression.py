"""AUTH-04 D-04 regression: every jwt.decode() call MUST specify algorithms=[].

Scoped to backend/app/ per Phase 3/4 precedent (test_session_query_regression.py).
Guards against the CWE-327 / "alg: none" vulnerability class — if a future PR
adds a bare jwt.decode(token, key) call, this test fails at CI.

Companion tests: test_session_query_regression.py, test_pydantic_v1_regression.py,
test_logger_migration_regression.py.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"

_DECODE_PATTERN = re.compile(r"\bjwt\.decode\(")
_ALG_PATTERN = re.compile(r"algorithms\s*=\s*\[")


def test_every_jwt_decode_specifies_algorithms() -> None:
    offenders: list[tuple[str, int, str]] = []
    for pyfile in APP_DIR.rglob("*.py"):
        lines = pyfile.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if _DECODE_PATTERN.search(line):
                # Check same line + next 2 lines (multi-line statements)
                window = "\n".join(lines[lineno - 1 : lineno + 2])
                if not _ALG_PATTERN.search(window):
                    offenders.append((str(pyfile.relative_to(APP_DIR)), lineno, line.strip()))
    assert not offenders, "jwt.decode() calls without algorithms=[...] detected (CWE-327 risk):\n" + "\n".join(
        f"  {f}:{ln} -> {code}" for f, ln, code in offenders
    )


def test_the_app_decodes_only_through_decode_access_token() -> None:
    """After the `webbpulse.security` swap there are no raw `jwt.decode` calls left.

    The test above guards the shape of a call that no longer exists in `app/`:
    every decode now goes through `app.api.dependencies.auth.decode_access_token`,
    which passes `algorithms=[ALGORITHM]` in exactly one place. That is a stronger
    position than auditing call sites, but only while it stays true, so this pins
    it. A new bare `jwt.decode` would be caught by the test above; a new *decode
    helper* that forgets the algorithm list would not, and this is what notices
    the import reappearing at all.
    """
    offenders: list[str] = []
    for pyfile in APP_DIR.rglob("*.py"):
        for lineno, line in enumerate(pyfile.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("import jwt", "from jwt import")):
                offenders.append(f"  {pyfile.relative_to(APP_DIR)}:{lineno} -> {stripped}")
    assert not offenders, (
        "PyJWT is imported directly in app/ again. Decoding belongs in "
        "app.api.dependencies.auth.decode_access_token, which is the one place "
        "the algorithm list is set:\n" + "\n".join(offenders)
    )
