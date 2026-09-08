"""What each entrypoint may import, and what it may need to start.

Two properties, and both are about the deployed image rather than about the
response a route returns.

**A domain image carries one domain.** A single module-scope import in the
composition wiring would pull all nine domains into every image: every route
would still answer, the whole suite would still pass, and the only symptom would
be that the `media` function pays `catalog`'s import on every cold start and
ships code it has no IAM to use. Reading the source cannot see that; only
reading `sys.modules` after the fact can, so these tests run each entrypoint in a
fresh interpreter and inspect what actually got imported.

**A domain image starts with nothing.** The functions run with no AWS
credentials during a cold start's import phase, and `vehicles` is meant to run
with no `secretsmanager:GetSecretValue` grant at all. If building the application
reads a secret, the function does not start, and it does not start in a way that
produces no application logs, because it fails before logging is configured.

So the subprocesses run under a stripped environment: no `AWS_*`, no
credentials, no region, nothing but what the settings class defaults. They also
run with `APP_SECRETS_ARN` pointing at an ARN that cannot be read, which is the
sharper version of the same test: a build that tried to resolve a secret would
not merely find nothing, it would attempt a network call and fail.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404 - fixed argv, no shell, no user input
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from app.composition.domains import DOMAIN_NAMES, ENTRYPOINT_MODULES

BACKEND = Path(__file__).resolve().parents[2]

# An ARN that is syntactically valid and belongs to an account that does not
# exist, so any attempt to resolve it is a network call that fails rather than a
# quiet miss.
UNREADABLE_SECRET_ARN = "arn:aws:secretsmanager:us-west-2:000000000000:secret:carmodpicker-nonexistent-AAAAAA"

# Build the application, then report which endpoint modules ended up imported
# and how many routes it serves. Printed as JSON on the last line so a
# import-time log line on stdout cannot corrupt the result.
PROBE = """
import json, sys
from app.entrypoints import {module} as entrypoint

app = entrypoint.build_app()
endpoints = sorted(
    name
    for name in sys.modules
    if name.startswith("app.api.endpoints.") and name.count(".") == 3
)
print(json.dumps({{
    "endpoints": endpoints,
    "routes": len(app.routes),
    "domain": entrypoint.DOMAIN.name,
    "service_name": entrypoint.DOMAIN.service_name,
    "requires_secrets": list(entrypoint.DOMAIN.requires_secrets),
}}))
"""


def _run(code: str, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Run one snippet in a fresh interpreter with an all but empty environment.

    The stripped environment is the point of the test, so the only variables set
    are the ones the interpreter itself needs: `PATH`, and `PYTHONPATH` so `app`
    is importable without an installed distribution.
    """
    environment = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(BACKEND),
        # Otherwise a `.pyc` write into a read-only tree is a hard failure, and
        # the Lambda filesystem is read-only outside `/tmp`.
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    environment.update(env or {})
    result = subprocess.run(  # nosec B603 - fixed argv, no shell
        [sys.executable, "-c", code],
        cwd=str(BACKEND),
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"subprocess failed with an empty environment:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def probes() -> Dict[str, Dict[str, Any]]:
    """One subprocess per domain, reused across the tests in this module."""
    return {
        domain: _run(
            PROBE.format(module=ENTRYPOINT_MODULES[domain]),
            env={"APP_SECRETS_ARN": UNREADABLE_SECRET_ARN},
        )
        for domain in DOMAIN_NAMES
    }


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_an_entrypoint_builds_with_no_credentials(domain: str, probes: Dict[str, Dict[str, Any]]) -> None:
    """The stripped run already asserted this by not raising; this names it.

    A failure here is a function that cannot cold start, which is worth being
    its own test rather than an implicit precondition of the next one.
    """
    assert probes[domain]["routes"] > 0
    assert probes[domain]["domain"] == domain


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_an_entrypoint_imports_only_its_own_endpoint_modules(domain: str, probes: Dict[str, Dict[str, Any]]) -> None:
    """The claim that makes nine images smaller than nine copies of one image."""
    from app.composition.domains import DOMAINS

    # Reconstruct what this domain is allowed to import by calling its own
    # loader in this process. An `APIRouter` is a `fastapi.routing` object and
    # says nothing about where it was built, so the defining module is taken
    # from the route handlers it carries instead.
    #
    # `auth/*` and `admin/*` are four-segment module names while the probe
    # records three-segment ones, so both sides are truncated to the same depth:
    # `app.api.endpoints.auth` stands for all four auth modules.
    expected = sorted(
        {
            ".".join(route.endpoint.__module__.split(".")[:4])
            for router, _, _ in DOMAINS[domain].load_routers()
            for route in router.routes
            if getattr(route, "endpoint", None) is not None
            and route.endpoint.__module__.startswith("app.api.endpoints.")
        }
    )
    imported = probes[domain]["endpoints"]
    assert imported, f"{domain} imported no endpoint module at all"
    assert imported == expected, f"{domain} imported {imported}, but owns {expected}"


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_an_entrypoint_reports_its_own_service_name(domain: str, probes: Dict[str, Dict[str, Any]]) -> None:
    assert probes[domain]["service_name"] == f"carmodpicker-{domain}"


def test_vehicles_is_the_domain_that_needs_no_secret(probes: Dict[str, Dict[str, Any]]) -> None:
    """The least-privilege claim the split rests on, asserted rather than assumed.

    Every route under `/api/car-generations` and `/api/search` is a public read,
    because `car_generations` disables the writing endpoints of its
    `BaseDynamoEndpointRouter`, so the generated routes that would depend on
    `get_current_user` are never registered. If a route that verifies a token
    ever lands in `vehicles`, this fails and the Terraform grant has to follow.
    """
    assert probes["vehicles"]["requires_secrets"] == []
    for domain in DOMAIN_NAMES:
        if domain != "vehicles":
            assert probes[domain]["requires_secrets"] == [
                "SECRET_KEY"
            ], f"{domain} verifies tokens and must name SECRET_KEY"


def test_importing_the_descriptors_imports_no_endpoint_module() -> None:
    """`load_routers` is a callable so that this stays true.

    If any descriptor's routers were imported at module scope, every entrypoint
    would import all nine domains through `app.composition.domains` and the
    isolation above would be accidental rather than structural.
    """
    result = _run(
        "import json, sys\n"
        "import app.composition.domains\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('app.api.endpoints'))))\n"
    )
    assert result == []


def test_no_entrypoint_imports_the_monolith_composition_root() -> None:
    """The split does not run through `app.main`.

    `app.main` is the whole-surface application the monolith serves. If an
    entrypoint imported it, every domain image would build all nine domains at
    import time.
    """
    for domain in DOMAIN_NAMES:
        source = (BACKEND / "app" / "entrypoints" / f"{ENTRYPOINT_MODULES[domain]}.py").read_text()
        assert "app.main" not in source
        assert "from ..main" not in source


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_an_entrypoint_exposes_the_runtime_wiring(domain: str) -> None:
    """`main` is what the process runs, and `handler` is what Lambda calls.

    Asserted by reading the module rather than by calling `main`, because it
    binds a port and replaces the root log handlers, and a test that ran it
    would leave both in place for every test after it.
    """
    module = __import__(f"app.entrypoints.{ENTRYPOINT_MODULES[domain]}", fromlist=["main"])
    assert callable(module.build_app)
    assert callable(module.main)
    # Mangum, matching `app/lambda_handler.py`. The Web Adapter switch is a
    # later PR; if this changes, the deploy workflow changes with it.
    assert module.handler is not None
    source = Path(module.__file__).read_text()
    for helper in ("configure_logging", "init_sentry", "check_signing_key"):
        assert helper in source, f"{domain} entrypoint does not call {helper}"
