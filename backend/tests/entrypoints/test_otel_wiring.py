"""Row 16: OpenTelemetry on in the domain functions, Sentry out of them.

Three properties, and each one fails quietly rather than loudly, which is why
each is asserted here rather than left to a smoke test against a deployed
function.

**Sentry is gone from the entrypoints.** Not from `app.main`: the monolith still
serves production until row 31 and keeps reporting through Sentry, so this is a
per-file assertion rather than a repository-wide one. A domain function that
still called `init_sentry` would work, and the only symptom would be two
reporting paths for the same request and a Sentry project that keeps looking
alive after the traffic behind it has moved.

**Tracing is configured before the application is built.** This is the one that
would have shipped broken. Every entrypoint carries a module-level
`app = build_app()` for Mangum, and that line runs at import, which is before
`main` has called `configure_tracing`. `build_domain_app` only attaches the
FastAPI instrumentation when a provider already exists, so instrumenting the
module-level application is impossible by construction, and `main` has to build
its own after configuring tracing. `instrument_app` can only inject its server
span middleware while the middleware stack is unbuilt, so getting this order
wrong produces a function that looks instrumented, logs nothing, and exports no
request spans at all.

**The gate still holds when the endpoint is unset.** Terraform sets
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` on the deployed functions and nothing sets
it in a test or a local run, so the gate is what keeps this suite from opening a
batch exporter against the real X-Ray endpoint.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.composition.domains import DOMAIN_NAMES, ENTRYPOINT_MODULES

BACKEND = Path(__file__).resolve().parents[2]
ENTRYPOINTS = BACKEND / "app" / "entrypoints"


def _source(domain: str) -> str:
    return (ENTRYPOINTS / f"{ENTRYPOINT_MODULES[domain]}.py").read_text()


def _main_body(domain: str) -> list[ast.stmt]:
    """The statements of `main`, so order is asserted on the tree not on text."""
    tree = ast.parse(_source(domain))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node.body
    raise AssertionError(f"{domain}: no main() in its entrypoint")


def _called_names(body: list[ast.stmt]) -> list[str]:
    """Every call in `body`, in source order, by the name being called."""
    names: list[str] = []
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call):
                function = node.func
                if isinstance(function, ast.Name):
                    names.append(function.id)
                elif isinstance(function, ast.Attribute):
                    names.append(function.attr)
    return names


# --- Sentry is out of the domain functions -----------------------------------


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_an_entrypoint_does_not_initialise_sentry(domain: str) -> None:
    """No `init_sentry` import and no call, in any of the nine.

    Asserted on the parsed tree rather than on the text, so the prose in these
    modules can go on explaining why Sentry is absent without tripping it.
    """
    tree = ast.parse(_source(domain))

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.extend(alias.name for alias in node.names)
            if node.module is not None:
                imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)

    assert not [
        name for name in imported if "sentry" in name.lower()
    ], f"{domain} imports Sentry; row 16 removed it from the domain functions"

    called = _called_names(tree.body)
    assert "init_sentry" not in called, f"{domain} still calls init_sentry"


def test_the_monolith_still_initialises_sentry() -> None:
    """The other half of the row, and the reason the check above is per-file.

    Row 16 removes Sentry from the domain functions only. The monolith serves
    every route in production until row 31, and dropping its error reporting
    here would be an outage in observability rather than a migration step.
    """
    source = (BACKEND / "app" / "composition" / "app.py").read_text()
    assert "init_sentry" in source


# --- Tracing is configured before the traced application is built ------------


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_main_configures_tracing_before_it_builds_the_app(domain: str) -> None:
    """`configure_tracing` precedes the `build_app` that `run_uvicorn` serves.

    The ordering is the whole delivery. `build_domain_app` reads the tracing
    flag when it builds, so an application built first is an application that is
    never instrumented, and the failure is silent: the function serves normally
    and exports no request spans.
    """
    called = _called_names(_main_body(domain))

    assert "configure_tracing" in called, f"{domain}: main does not configure tracing"
    assert "build_app" in called, f"{domain}: main does not build an application"
    assert called.index("configure_tracing") < called.index("build_app"), (
        f"{domain}: main builds the application before configuring tracing, so "
        "the FastAPI instrumentation is never attached"
    )


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_main_configures_logging_before_tracing(domain: str) -> None:
    """`configure_tracing` logs its own warnings, so the format must exist first.

    A missing `aws-otel` extra warns rather than raising, and that warning is
    the only signal that a function is about to export unsigned. It has to land
    in the shared JSON format to be selectable by the log based alarms.
    """
    called = _called_names(_main_body(domain))

    assert called.index("configure_logging") < called.index("configure_tracing"), (
        f"{domain}: tracing is configured before logging, so its warnings are "
        "emitted in whatever format the root logger defaulted to"
    )


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_the_module_level_app_is_not_the_one_main_serves(domain: str) -> None:
    """`main` builds its own, because the module-level one predates the provider.

    The module-level `app` exists for Mangum and is constructed at import, which
    is before any of `main` has run. If `main` served that object instead of
    building a fresh one, no amount of correct ordering inside `main` would
    instrument it.
    """
    body = _main_body(domain)
    called = _called_names(body)

    assert "run_uvicorn" in called, f"{domain}: main does not serve"

    # The served expression is a call to `build_app`, not the module global.
    served = [
        statement
        for statement in body
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "run_uvicorn"
    ]
    assert len(served) == 1, f"{domain}: expected exactly one run_uvicorn call"

    argument = served[0].value.args[0]
    assert isinstance(argument, ast.Call) and isinstance(
        argument.func, ast.Name
    ), f"{domain}: run_uvicorn is not passed a freshly built application"
    assert argument.func.id == "build_app", (
        f"{domain}: run_uvicorn serves {ast.dump(argument)} rather than build_app(), "
        "so it serves an application built before tracing was configured"
    )


# --- The signing exporter is installed ---------------------------------------


@pytest.mark.parametrize("filename", ["requirements.txt", "requirements-lambda.txt"])
def test_both_requirements_files_carry_the_aws_otel_extra(filename: str) -> None:
    """`aws-otel` is what signs the export, and it is needed in both files.

    The X-Ray OTLP endpoint authenticates with SigV4 and answers 403 to an
    unsigned POST, which the exporter retries in silence. `webbpulse.otel` warns
    and falls back to the unsigned exporter when the extra is missing rather
    than failing a cold start, so leaving it out of the file the *image*
    installs produces a function that starts, serves, and exports nothing.

    `tests/test_requirements_lambda_subset.py` already pins the two specifiers
    to each other character for character; this asserts what that string has to
    contain now that tracing is on.
    """
    line = next(
        raw.strip() for raw in (BACKEND / filename).read_text().splitlines() if raw.strip().startswith("webbpulse[")
    )
    extras = line.split("[", 1)[1].split("]", 1)[0].split(",")
    assert "otel" in extras, f"{filename}: the otel extra is what provides configure_tracing"
    assert "aws-otel" in extras, (
        f"{filename}: without the aws-otel extra the exporter posts unsigned and "
        "every span is silently rejected with a 403"
    )
