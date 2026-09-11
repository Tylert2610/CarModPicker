"""Which repositories a domain's process carries, and which it cannot reach.

Section 2.3 of `docs/migration/split-plan.md` names the `Repositories` singleton
as the blocker: twenty-five repositories constructed at module import, reached by
every route, so every one of the nine functions would have imported the whole
data layer at cold start and held a live `UserRepository` pointed at a table it
has no IAM grant for. This module is what stops that coming back.

Four claims, in order of what they protect.

**A domain declares the repositories its own code reaches, and no others.** The
tuples in `app/composition/domains.py` are recomputed here from the real import
graph, so a tuple that grew a repository nothing uses fails, and so does one
missing a repository a route reaches. The first is an IAM grant the function
does not need; the second is a `RepositoryNotInBundle` in production on whichever
route reaches it first. Neither is visible by reading the tuple.

**A bundle refuses what it does not carry.** Attribute access outside the
declared set raises rather than returning something, and the message names the
table, because the next question is always which grant is missing.

**Building a domain's application constructs no repository, and importing it
imports no other domain's data modules.** Asserted in a fresh interpreter, the
same way `test_entrypoint_isolation.py` asserts the endpoint modules, because a
single eager construction in the wiring would undo it while every test still
passed.

**Root A still carries all twenty-five.** The monolith serves every route and
must keep every repository, so the union of the nine bundles is the whole set and
the application `app.main` exposes resolves to it.

## Why the plan's ownership column is not the assertion

Section 1.2 gives each table one owner, and a bundle is deliberately wider than
that. The difference is section 1.3's cross-domain reads, which the plan leaves
synchronous: `media` owns `image_source_mappings` and reads four more tables for
the orphan sweep, `vehicles` owns the three car tables and reads thirteen more
for search. Asserting the bundle equals the ownership column would fail on
exactly the reads the plan says to keep, so the ownership column is asserted
where it belongs instead: every table has an owner, every owner carries it, and
the reads on top are listed here by name so that a new one is a decision rather
than a drift.
"""

from __future__ import annotations

import ast
import json
import subprocess  # nosec B404 - fixed argv, no shell, no user input
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set

import pytest

from app.api.dependencies.repositories import (
    ALL_REPOSITORY_NAMES,
    RepositoryBundle,
    RepositoryNotInBundle,
    build_bundle,
    get_repositories,
)
from app.composition.domains import DOMAIN_NAMES, DOMAINS, ENTRYPOINT_MODULES
from app.db.dynamo.registry import REPOSITORY_SPECS

BACKEND = Path(__file__).resolve().parents[2]

# The same unreadable ARN `test_entrypoint_isolation.py` uses: syntactically
# valid, in an account that does not exist, so an attempt to resolve it is a
# failed network call rather than a quiet miss.
UNREADABLE_SECRET_ARN = "arn:aws:secretsmanager:us-west-2:000000000000:secret:carmodpicker-nonexistent-AAAAAA"


# --- Section 1.2's ownership column, transcribed ------------------------------
# Table suffix to the domain that owns it. Twenty-five rows, one owner each,
# copied from the plan rather than derived, so that a code change cannot quietly
# rewrite what the plan says. `tests` reads it in both directions: every table
# has exactly one owner, and the owning domain's bundle carries it.

TABLE_OWNERS: Dict[str, str] = {
    "users": "users",
    "oauth_accounts": "identity",
    "webauthn_credentials": "identity",
    "app_settings": "users",
    "parts": "catalog",
    "part_cars": "catalog",
    "part_listings": "catalog",
    "part_price_history": "catalog",
    "part_manufacturers": "catalog",
    "categories": "catalog",
    "retailers": "catalog",
    "car_makes": "vehicles",
    "car_models": "vehicles",
    "car_generations": "vehicles",
    "build_lists": "build-lists",
    "build_list_parts": "build-lists",
    "build_list_phases": "build-lists",
    "build_list_labor_estimates": "build-lists",
    "build_logs": "build-logs",
    "build_log_posts": "build-logs",
    "votes": "moderation",
    "reports": "moderation",
    "bug_reports": "moderation",
    "part_price_alerts": "admin",
    "image_source_mappings": "media",
}

# The cross-domain reads section 1.3 leaves synchronous, per domain: repositories
# a domain carries that another domain owns. Listed by name so that a new one is
# a deliberate edit here with a reason, rather than a tuple quietly widening.
#
# Rows 22 onward of section 8 are what remove these, and row 28 is the first row
# that actually did. Seam 2 came out of four domains at once: `catalog`,
# `vehicles`, `build-lists` and `admin` all carried some of `build_list_parts`,
# `reports` and `part_price_alerts` only because their delete routes called
# `purge_related_rows_for_parts`. The rest of the list is still outstanding, and
# `test_no_cross_domain_read_is_undeclared` is what keeps it honest meanwhile.
EXPECTED_CROSS_DOMAIN_READS: Dict[str, Set[str]] = {
    # `identity` writes `users` on oauth link, webauthn registration, and
    # password and 2FA changes. Seam 1's neighbour; stays until the tombstone.
    "identity": {"users"},
    # Row 30 took seam 1 out of this set, which is the largest single narrowing
    # in the plan: twenty tables across five domains, written by the delete
    # cascade on the request thread, now written by
    # `carmodpicker-<env>-users-delete-consumer` instead.
    #
    # `oauth_accounts` is what is left, and it is a real read rather than a
    # remnant: `user_service.user_read` attaches a user's linked accounts to
    # every user response. It was not in this set before row 30 and it should
    # have been. `_bundle_accesses` matches a receiver named `repos`, and that
    # module read the bundle through a local named `repositories`, so the graph
    # never saw it; the cascade declared the repository for unrelated reasons
    # and hid the gap. Row 30 renamed the local, which is why a table appears
    # here on the row that removes twenty.
    "users": {"oauth_accounts"},
    # Row 28 took seam 2 out of this set. `build_list_parts`, `reports` and
    # `part_price_alerts` were here because the synchronous part purge wrote
    # them; the purge consumer names them now. What is left is `votes`, read by
    # row 24's `net_votes` consumer, `users`, read by seam 4's price alert
    # email, and the car tables `part_service` reads to infer fitment.
    "catalog": {
        "users",
        "car_makes",
        "car_models",
        "car_generations",
        "votes",
    },
    # Seam 5's search fan-out: one route reading four domains' tables. Stays
    # synchronous because turning it into service calls makes one Dynamo round
    # trip into three or four HTTP hops on a path that is already slow.
    "vehicles": {
        "users",
        "categories",
        "part_manufacturers",
        "retailers",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "build_lists",
        "votes",
    },
    # Price capture writes `part_listings` and `part_price_history`; a build log
    # is created with the list; the rest are joins for the rendered list.
    "build-lists": {
        "users",
        "car_makes",
        "car_models",
        "car_generations",
        "categories",
        "part_manufacturers",
        "retailers",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "build_logs",
        "build_log_posts",
        "votes",
    },
    # The parent list and the author.
    "build-logs": {"users", "build_lists"},
    # Seam 3, the `net_votes` denormalisation, is the `parts` write, and it is
    # the only cross-domain write `moderation` has. Row 24 inverts it into a
    # stream handler `catalog` owns, after which `moderation` has none.
    "moderation": {"users", "car_makes", "car_models", "car_generations", "parts", "build_lists"},
    # Seam 5's orphan sweep: five full table scans to find unreferenced S3
    # objects. Read-only, admin-initiated, and the narrowest bundle in the map.
    "media": {"users", "car_generations", "parts", "build_lists"},
    # `admin/stats` counts twelve tables and `admin/db_ops` seeds and purges, so
    # `admin` reads most of the application by design. That breadth is why
    # section 1.5's preferred name won: this is administration, not ingestion.
    "admin": {
        "users",
        "oauth_accounts",
        "webauthn_credentials",
        "car_makes",
        "car_models",
        "car_generations",
        "categories",
        "part_manufacturers",
        "retailers",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "build_lists",
        "build_list_phases",
        "build_logs",
        "votes",
        "reports",
        "image_source_mappings",
    },
}


# --- Recomputing a domain's reachable repositories ----------------------------
# The tuples in `domains.py` are a claim about the import graph, and this is the
# graph. Read statically with `ast` rather than by importing, because importing
# nine domains into one interpreter would union their module sets and the
# question here is per domain.


def _module_file(module: str) -> Optional[Path]:
    candidate = BACKEND / (module.replace(".", "/") + ".py")
    if candidate.exists():
        return candidate
    package = BACKEND / module.replace(".", "/") / "__init__.py"
    return package if package.exists() else None


def _app_imports(tree: ast.AST, module: str) -> Set[str]:
    """The `app.*` modules one module imports, including `from x import y` where
    `y` is itself a module rather than a name."""
    found: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
            found.add(node.module)
            for alias in node.names:
                submodule = f"{node.module}.{alias.name}"
                if _module_file(submodule) is not None:
                    found.add(submodule)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names if alias.name.startswith("app"))
    return {name for name in found if _module_file(name) is not None}


def _bundle_accesses(tree: ast.AST) -> Set[str]:
    """Every `<something>.<repository>` where `<something>` is a bundle.

    Two spellings, and both are common. Endpoints take the bundle as a parameter
    and write `repos.users`; services hold it on the instance and write
    `self.repos.users`. Matching the attribute name alone would be too loose,
    because `part.categories` and `payload.users` are ordinary attributes on
    unrelated objects, so the receiver has to be a bundle: either the name
    `repos` or an attribute access ending in `.repos`.
    """
    found: Set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr not in REPOSITORY_SPECS:
            continue
        receiver = node.value
        if isinstance(receiver, ast.Name) and receiver.id == "repos":
            found.add(node.attr)
        elif isinstance(receiver, ast.Attribute) and receiver.attr == "repos":
            found.add(node.attr)
    return found


#: Modules a domain reaches without any route of its own naming them.
#:
#: The scanner below walks out from the endpoint modules a domain's loader
#: imports. That is the whole story for eight domains. `identity` is the
#: exception since row 13 of `docs/identity-adoption.md` deleted its 24 legacy
#: routes: it now loads no router of its own, and every route it serves belongs
#: to `webbpulse.identity`. It still reads and writes three tables, through the
#: hooks and stores CarModPicker hands the package at composition time, so the
#: bundle it declares is real and the roots that justify it are these rather
#: than an endpoint module.
#:
#: `identity_hooks.py` constructs its repositories directly rather than through
#: a bundle, because the package calls the hooks outside any request, so
#: `_bundle_accesses` cannot see them. The names are taken from the constructor
#: defaults there instead, which is why this mapping is by repository name and
#: not a module to scan.
EXTRA_REACHABLE: Dict[str, Set[str]] = {
    "identity": {"users", "oauth_accounts", "webauthn_credentials"},
}


def _reachable_repositories(domain: str) -> Set[str]:
    """Every `repos.<name>` any module the domain's routers reach can perform.

    The transitive closure of the domain's endpoint modules over `app.*` imports,
    scanned for attribute accesses on the bundle. It over-approximates, because a
    module that imports another for one helper is credited with all of that
    module's repository accesses, and that is the right direction to err: the
    bundle has to carry whatever a route might reach, and a repository this finds
    but no request ever touches costs an unused entry rather than a 500.

    `app.api.services.__init__` re-exports `ReportService` and `VoteService`, so
    any domain importing anything from `app.api.services` is credited with both.
    That is real: the modules are imported into the process either way.
    """
    roots: Set[str] = set()
    source = ast.parse(_read_loader_source(domain))
    for node in ast.walk(source):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.api.endpoints"):
            for alias in node.names:
                candidate = f"{node.module}.{alias.name}"
                roots.add(candidate if _module_file(candidate) is not None else node.module)

    seen: Set[str] = set()
    stack = list(roots)
    accesses: Set[str] = set()
    while stack:
        module = stack.pop()
        if module in seen:
            continue
        path = _module_file(module)
        if path is None:
            continue
        seen.add(module)
        text = path.read_text()
        tree = ast.parse(text)
        accesses |= _bundle_accesses(tree)
        stack.extend(_app_imports(tree, module))
    return accesses | EXTRA_REACHABLE.get(domain, set())


def _read_loader_source(domain: str) -> str:
    import inspect

    return inspect.getsource(DOMAINS[domain].load_routers).strip()


# --- The declared tuples match the code ---------------------------------------


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_a_domain_declares_every_repository_its_routes_reach(domain: str) -> None:
    """A missing entry is a `RepositoryNotInBundle` in production.

    It would not fail at build time and it would not fail on most routes; it
    would fail on the one route that reaches the repository, once that route is
    served by the domain function rather than by the monolith.

    For `identity` it would fail outside a route entirely, on the first
    registration or sign in the package handles, because the reach is through
    the hooks rather than through a route. See `EXTRA_REACHABLE`.
    """
    declared = set(DOMAINS[domain].repositories)
    reachable = _reachable_repositories(domain)
    missing = sorted(reachable - declared)
    assert missing == [], f"{domain} reaches {missing} but does not declare them"


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_a_domain_declares_no_repository_its_routes_cannot_reach(domain: str) -> None:
    """A surplus entry is a DynamoDB grant the function does not need.

    Harmless to the application and exactly the thing the split is meant to
    remove, so it fails here rather than being noticed in an IAM policy review
    that may not happen.
    """
    declared = set(DOMAINS[domain].repositories)
    reachable = _reachable_repositories(domain)
    surplus = sorted(declared - reachable)
    assert surplus == [], f"{domain} declares {surplus} but no route reaches them"


# --- The plan's ownership column ----------------------------------------------


def test_every_table_has_exactly_one_owner() -> None:
    """Section 1.2's column, checked against the repository registry.

    A repository added without a plan row, or a plan row without a repository,
    fails here rather than surfacing later as a table nobody grants access to.
    """
    registry_tables = {spec.table for spec in REPOSITORY_SPECS.values()}
    assert sorted(registry_tables) == sorted(TABLE_OWNERS)
    assert len(REPOSITORY_SPECS) == 25
    assert set(TABLE_OWNERS.values()) <= set(DOMAIN_NAMES)


@pytest.mark.parametrize("table,owner", sorted(TABLE_OWNERS.items()))
def test_the_owning_domain_carries_the_table_it_owns(table: str, owner: str) -> None:
    """An owner that cannot reach its own table cannot serve its own routes."""
    assert table in DOMAINS[owner].tables, f"{owner} owns {table} but its bundle does not carry it"


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_no_cross_domain_read_is_undeclared(domain: str) -> None:
    """Every repository a domain carries is either its own or a listed seam.

    This is the test that keeps the cross-domain surface honest while rows 22
    onward are outstanding. A bundle that grows a repository another domain owns
    fails until the reason is written down next to the seam it belongs to.
    """
    owned = {name for name, spec in REPOSITORY_SPECS.items() if TABLE_OWNERS[spec.table] == domain}
    borrowed = set(DOMAINS[domain].repositories) - owned
    assert borrowed == EXPECTED_CROSS_DOMAIN_READS[domain], (
        f"{domain}'s cross-domain reads changed. "
        f"Added: {sorted(borrowed - EXPECTED_CROSS_DOMAIN_READS[domain])}. "
        f"Removed: {sorted(EXPECTED_CROSS_DOMAIN_READS[domain] - borrowed)}."
    )


def test_media_is_the_narrowest_bundle() -> None:
    """The first domain the plan cuts, and the one worth naming outright.

    `media` owns one table and reads four. If this ever grows, the first
    function to be cut over stops being the cheap one to verify, and the reason
    should be written down before it does.
    """
    media = DOMAINS["media"]
    assert media.tables == (
        "build_lists",
        "car_generations",
        "image_source_mappings",
        "parts",
        "users",
    )
    assert len(media.repositories) == 5
    assert min(len(DOMAINS[d].repositories) for d in DOMAIN_NAMES) == 3  # identity


# --- The bundle's own behaviour -----------------------------------------------


def test_a_bundle_refuses_a_repository_it_does_not_carry() -> None:
    """And the message names the table, because that is the next question."""
    bundle = build_bundle(DOMAINS["media"].repositories, name="media")
    with pytest.raises(RepositoryNotInBundle) as raised:
        bundle.app_settings
    assert raised.value.repository == "app_settings"
    assert raised.value.table == "app_settings"
    assert "app_settings" in str(raised.value)
    assert "media" in str(raised.value)


def test_the_refusal_is_an_attribute_error() -> None:
    """So `getattr(repos, name, None)` and `hasattr` keep working.

    Only an unguarded access becomes the loud failure; code that already asks
    whether a repository is present keeps its answer.
    """
    bundle = build_bundle(DOMAINS["media"].repositories, name="media")
    assert issubclass(RepositoryNotInBundle, AttributeError)
    assert getattr(bundle, "app_settings", None) is None
    assert not hasattr(bundle, "app_settings")


def test_a_bundle_builds_nothing_until_a_repository_is_asked_for() -> None:
    """Laziness is the property that makes a cold start proportional."""
    bundle = build_bundle(DOMAINS["media"].repositories, name="media")
    assert "built=[]" in repr(bundle)
    first = bundle.image_source_mappings
    assert "image_source_mappings" in repr(bundle)
    # Memoised, so every route in the process shares one instance exactly as the
    # module-level singleton did.
    assert bundle.image_source_mappings is first


def test_an_unknown_repository_name_is_rejected_when_the_bundle_is_built() -> None:
    """A typo in a domain's tuple fails at build rather than on one route."""
    with pytest.raises(ValueError, match="typo_repository"):
        build_bundle(("users", "typo_repository"), name="broken")


def test_the_bundle_reports_the_tables_it_can_reach() -> None:
    """What a Terraform IAM policy for the domain has to cover."""
    bundle = build_bundle(DOMAINS["build-logs"].repositories, name="build-logs")
    assert bundle.tables == ("build_lists", "build_log_posts", "build_logs", "users")
    assert bundle.repository_names == DOMAINS["build-logs"].repositories


# --- Root A keeps everything --------------------------------------------------


def test_the_union_of_the_nine_bundles_is_all_twenty_five() -> None:
    """Root A serves every route, so it must keep every repository.

    A repository in no domain's tuple is one no function could reach after the
    cut, which is either a dead repository or a route that would 500.
    """
    union: Set[str] = set()
    for domain in DOMAIN_NAMES:
        union |= set(DOMAINS[domain].repositories)
    assert union == set(ALL_REPOSITORY_NAMES)
    assert len(ALL_REPOSITORY_NAMES) == 25


def test_root_a_binds_a_bundle_carrying_all_twenty_five() -> None:
    """The monolith is unchanged by this PR, and that is the point.

    `app.main` still exposes every route and every repository behind them, so
    the split can proceed one domain at a time with the monolith serving the
    rest.
    """
    from app.api.dependencies.repositories import get_repositories as dependency
    from app.main import app

    override = app.dependency_overrides.get(dependency)
    assert override is not None, "Root A did not bind a repository bundle"
    bundle = override()
    assert isinstance(bundle, RepositoryBundle)
    assert set(bundle.repository_names) == set(ALL_REPOSITORY_NAMES)


def test_the_process_default_is_the_full_set() -> None:
    """For `scripts/`, `init_cars`, `init_categories` and `car_inference`.

    They call `get_repositories()` outside any request and outside any
    application, and they are not part of the split. Making the default the full
    set is what lets them keep working untouched; every deployed function is
    built by a composition root, which binds, so the default is never what a
    function serves.
    """
    assert set(get_repositories().repository_names) == set(ALL_REPOSITORY_NAMES)


def test_building_one_domain_does_not_disturb_another() -> None:
    """Bundles are bound per application, not installed per process.

    The route contract test builds all nine Root B applications in one
    interpreter. If binding were a module-level install, whichever was built
    last would serve every test after it.
    """
    import importlib

    media = importlib.import_module("app.entrypoints.media").build_app()
    users = importlib.import_module("app.entrypoints.users").build_app()

    from app.api.dependencies.repositories import get_repositories as dependency

    media_bundle = media.dependency_overrides[dependency]()
    users_bundle = users.dependency_overrides[dependency]()
    assert set(media_bundle.repository_names) == set(DOMAINS["media"].repositories)
    assert set(users_bundle.repository_names) == set(DOMAINS["users"].repositories)
    assert "app_settings" in users_bundle.repository_names
    assert "app_settings" not in media_bundle.repository_names


# --- The fresh-interpreter claims ---------------------------------------------
# Everything above runs in the test process, where all nine domains are imported
# and every `app.db.dynamo` module is already in `sys.modules`. These two run in
# a stripped subprocess, because the claim is about what a cold start imports and
# only a fresh interpreter can see it.


def _run(code: str, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    environment = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(BACKEND),
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


BUNDLE_PROBE = """
import json, sys
from app.entrypoints import {module} as entrypoint
from app.api.dependencies.repositories import get_repositories

app = entrypoint.build_app()
bundle = app.dependency_overrides[get_repositories]()
print(json.dumps({{
    "declared": sorted(bundle.repository_names),
    "tables": sorted(bundle.tables),
    "built": sorted(bundle._built),
    "dynamo_modules": sorted(
        name for name in sys.modules
        if name.startswith("app.db.dynamo.") and name.count(".") == 3
    ),
}}))
"""


@pytest.fixture(scope="module")
def bundle_probes() -> Dict[str, Dict[str, Any]]:
    return {
        domain: _run(
            BUNDLE_PROBE.format(module=ENTRYPOINT_MODULES[domain]),
            env={"APP_SECRETS_ARN": UNREADABLE_SECRET_ARN},
        )
        for domain in DOMAIN_NAMES
    }


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_building_a_domain_constructs_no_repository(domain: str, bundle_probes: Dict[str, Dict[str, Any]]) -> None:
    """The old singleton constructed twenty-five at import; this constructs none.

    A repository constructed at build time reaches the DynamoDB client during
    the cold start's import phase, which is exactly the work the split is meant
    to remove from a function that will never use it.
    """
    assert bundle_probes[domain]["built"] == []


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_a_domain_binds_exactly_its_own_bundle(domain: str, bundle_probes: Dict[str, Dict[str, Any]]) -> None:
    """In a fresh interpreter, with no credentials, as a cold start would."""
    assert bundle_probes[domain]["declared"] == sorted(DOMAINS[domain].repositories)
    assert bundle_probes[domain]["tables"] == sorted(DOMAINS[domain].tables)


def test_media_builds_without_importing_another_domains_data_modules(
    bundle_probes: Dict[str, Dict[str, Any]],
) -> None:
    """The claim in one sentence, for the domain the plan cuts first.

    `media`'s bundle carries five repositories drawn from four `app.db.dynamo`
    modules, and building its application must not import the ones behind the
    twenty it does not carry: `app_settings`, `bug_reports`, `part_price_alerts`
    and `build_logs` have no entry in its tuple at all, so importing them would
    mean something outside the bundle is pulling them in.
    """
    imported = set(bundle_probes["media"]["dynamo_modules"])
    for module in ("app_settings", "bug_reports", "part_price_alerts", "build_logs"):
        assert f"app.db.dynamo.{module}" not in imported, f"media imported app.db.dynamo.{module}"


def test_importing_the_registry_imports_no_repository_module() -> None:
    """`app.composition.domains` imports the registry in every function.

    The registry names twenty-five repositories as strings precisely so that
    reading the catalogue costs no import: if it held the classes, declaring a
    domain's tuple would pull in every repository module and the laziness above
    would be decorative.

    The shared base comes in regardless, because `app/db/dynamo/__init__.py`
    re-exports `DynamoRepository`, `TableSpec` and the error types, and importing
    any module in the package runs it. That base is what every domain uses; what
    must not appear is a module that defines repositories, since each one belongs
    to a domain and most domains want none of them.
    """
    #: The nine modules under `app.db.dynamo` that define repository classes.
    #: None of them may be imported by reading the registry.
    repository_modules = {f"app.db.dynamo.{spec.module}" for spec in REPOSITORY_SPECS.values()}
    assert len(repository_modules) == 9

    imported = _run(
        "import json, sys\n"
        "import app.db.dynamo.registry\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('app.db.dynamo.'))))\n"
    )
    assert sorted(repository_modules & set(imported)) == []
