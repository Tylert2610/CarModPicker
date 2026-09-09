"""`requirements-lambda.txt` must be a strict subset of `requirements.txt`.

Two files declare this application's dependencies and they are installed by
different things. `requirements.txt` is what CI installs and what the test suite
runs against; `requirements-lambda.txt` is what the deploy zip resolves for
manylinux x86_64 and what the per-domain container image installs. It is the
narrower of the two on purpose, carrying only the runtime packages: pytest,
black, moto and locust have no business in a Lambda image.

The failure mode this guards is quiet and expensive. A runtime dependency added
to `requirements.txt` alone passes every check, because every check installs
that file, and then fails at import inside the image, which is the first place
the package is actually missing. A pin that drifts between the two is worse
still: the suite then proves a version the image does not run, so a green build
says nothing about what deploys. Adopting `webbpulse` is exactly that kind of
change, which is why this test arrived with it.

"Strict subset" means both directions of one relationship. Every requirement in
the Lambda file must appear in `requirements.txt`, and the two specifiers must be
character-identical including extras, so `webbpulse[fastapi,otel]==0.2.0` in one
and `webbpulse==0.2.0` in the other is a failure rather than a near miss. The
reverse containment is deliberately not asserted: `requirements.txt` is expected
to hold more, and enumerating which extras are development-only here would
duplicate a judgement the two files already express.
"""

from __future__ import annotations

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FULL = BACKEND_DIR / "requirements.txt"
LAMBDA = BACKEND_DIR / "requirements-lambda.txt"


def _parse(path: Path) -> dict[str, str]:
    """Map a requirement's distribution name to the exact line that declared it.

    Keys are lowercased with underscores folded to hyphens, which is PEP 503
    normalisation and the reason `typing_extensions` and `typing-extensions`
    compare equal. Values keep the original line so a mismatch can report what
    each file actually says rather than only that they differ.
    """
    requirements: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        # Split the distribution name off the version specifier and any extras.
        # The specifier characters are the full set PEP 508 allows to start one,
        # so `>=2.68.1,<3` is handled as well as `==0.2.0`.
        name = line
        for separator in ("[", "=", ">", "<", "!", "~", ";"):
            name = name.split(separator, 1)[0]
        normalized = name.strip().lower().replace("_", "-")
        if normalized:
            requirements[normalized] = line
    return requirements


def test_lambda_requirements_are_a_subset_of_the_full_set() -> None:
    """Nothing may be pinned for the runtime that CI never installs."""
    full = _parse(FULL)
    lambda_only = sorted(set(_parse(LAMBDA)) - set(full))
    assert not lambda_only, (
        "requirements-lambda.txt pins packages absent from requirements.txt, so "
        "the test suite never exercises them: " + ", ".join(lambda_only)
    )


def test_shared_requirements_pin_identical_versions() -> None:
    """A package in both files must carry the same specifier in both.

    Compared on the whole line rather than the version alone, so a dropped extra
    is caught too. `webbpulse[fastapi,otel]` without `otel` in the Lambda file
    would leave `configure_tracing` unimportable the moment row 16 sets the
    endpoint variable, and nothing else would notice.
    """
    full = _parse(FULL)
    mismatched = {
        name: (spec, full[name]) for name, spec in _parse(LAMBDA).items() if name in full and spec != full[name]
    }
    assert not mismatched, "\n".join(
        f"{name}: requirements-lambda.txt has {lambda_spec!r}, requirements.txt has {full_spec!r}"
        for name, (lambda_spec, full_spec) in sorted(mismatched.items())
    )


def test_the_shared_package_is_installed_by_the_runtime_file() -> None:
    """`webbpulse` specifically must reach the image.

    The two tests above are general and would keep passing if the package were
    dropped from both files at once. The application imports `webbpulse` at
    module scope in `app/core/logging.py` and `app/core/config.py`, so its
    absence from the runtime file is a cold start crash rather than a degraded
    feature, and that is worth naming directly.
    """
    assert "webbpulse" in _parse(LAMBDA)
