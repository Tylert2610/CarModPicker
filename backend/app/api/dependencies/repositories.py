"""The repository bundle a process serves its routes from.

## What this replaces

This module used to define a frozen dataclass with twenty-five fields and
construct all twenty-five repositories at import. Every route in the application
depends on it, so every one of the nine functions in the split would have
imported the entire data layer on every cold start, and a `media` function would
have held a `UserRepository` pointed at a table it has no IAM grant for. Section
2.3 of `docs/migration/split-plan.md` calls that the blocker, and this is the
unwinding.

What replaces it is a bundle that declares which repositories it carries.
`app.composition.domains` gives each domain a `repositories` tuple, Root B builds
a bundle from one domain's tuple, and Root A builds one from all twenty-five. A
`media` process therefore imports `app.db.dynamo.image_source_mappings` and the
four modules its cross-domain reads need, and never imports
`app.db.dynamo.app_settings` at all.

## Why the route signatures did not change

`repos: Repositories = Depends(get_repositories)` appears on roughly two hundred
routes and helpers, and `Repositories` is used as a type annotation in every one
of them. Renaming it would have made this PR a rename of two hundred call sites
with a wiring change hidden inside, and it would have changed nothing about what
runs. So `Repositories` stays the name and stays the annotation; it is now a
bundle rather than a dataclass, and `RepositoryBundle` is the honest alias for
anyone writing new code. Because no signature and no schema changed, the OpenAPI
document is byte identical and `tests/test_openapi_snapshot.py` did not move.

## Why access to an undeclared repository raises

A bundle that quietly returned `None` for a repository outside its domain would
turn a wiring mistake into an `AttributeError` deep inside a request, in
production, on the one route that reaches it. Raising `RepositoryNotInBundle` on
attribute access turns the same mistake into a message that names the domain, the
repository and the table, and `tests/entrypoints/test_repository_bundles.py`
makes it fail in CI instead. The exception carries the table name because the
next question after "why can this not see `users`" is always "which grant is
missing".

## Laziness

Repositories are constructed on first access, not when the bundle is built.
Building `app.entrypoints.media`'s application therefore imports no
`app.db.dynamo` module beyond the ones its own routes touch when they run, which
is what `tests/entrypoints/test_repository_bundles.py` asserts in a fresh
interpreter. Construction is memoised per bundle, so a repository is built once
per process and every route sees the same instance, exactly as the module-level
singleton did.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Tuple

from app.db.dynamo.registry import ALL_REPOSITORY_NAMES, REPOSITORY_SPECS

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.db.dynamo.app_settings import AppSettingsRepository
    from app.db.dynamo.bug_reports import BugReportRepository
    from app.db.dynamo.build_lists import (
        BuildListLaborEstimateRepository,
        BuildListPartRepository,
        BuildListPhaseRepository,
        BuildListRepository,
    )
    from app.db.dynamo.build_logs import BuildLogPostRepository, BuildLogRepository
    from app.db.dynamo.catalog import (
        CarGenerationRepository,
        CarMakeRepository,
        CarModelRepository,
        CategoryRepository,
        PartCarRepository,
        PartListingRepository,
        PartManufacturerRepository,
        PartPriceHistoryRepository,
        PartRepository,
        RetailerRepository,
    )
    from app.db.dynamo.image_source_mappings import ImageSourceMappingRepository
    from app.db.dynamo.moderation import ReportRepository, VoteRepository
    from app.db.dynamo.part_price_alerts import PartPriceAlertRepository
    from app.db.dynamo.users import (
        OAuthAccountRepository,
        UserRepository,
        WebAuthnCredentialRepository,
    )


class RepositoryNotInBundle(AttributeError):
    """A route asked for a repository its own domain does not carry.

    An `AttributeError` subclass on purpose: `getattr(repos, name, None)` and
    `hasattr` keep behaving the way callers expect, and only an unguarded access
    becomes the loud failure it should be.
    """

    def __init__(self, bundle_name: str, repository: str) -> None:
        spec = REPOSITORY_SPECS.get(repository)
        if spec is None:
            message = f"{bundle_name!r} has no repository {repository!r}, and neither does any domain"
        else:
            message = (
                f"{bundle_name!r} does not carry the {repository!r} repository, "
                f"which owns the {spec.table!r} table. Either the route belongs to "
                f"another domain, or {bundle_name!r} needs {repository!r} added to "
                f"its `repositories` tuple in app/composition/domains.py and the "
                f"matching IAM grant in Terraform."
            )
        super().__init__(message)
        self.bundle_name = bundle_name
        self.repository = repository
        self.table = spec.table if spec is not None else None


class RepositoryBundle:
    """The repositories one process may use, built on first access.

    Attribute access is the whole interface, because that is what two hundred
    call sites already do: `repos.users.get(...)`. The declared names resolve to
    a memoised repository; every other name raises `RepositoryNotInBundle`.
    """

    __slots__ = ("_name", "_names", "_built", "_lock")

    def __init__(self, names: Iterable[str], *, name: str = "all") -> None:
        declared = tuple(dict.fromkeys(names))
        unknown = sorted(set(declared) - set(REPOSITORY_SPECS))
        if unknown:
            raise ValueError(f"{name!r} declares unknown repositories: {', '.join(unknown)}")
        self._name = name
        self._names = declared
        self._built: Dict[str, Any] = {}
        # Repositories are built on first access and FastAPI serves requests
        # from a thread pool, so two requests can race on the same first access.
        # Building twice would be harmless but wasteful; the lock makes the
        # bundle behave exactly like the module-level singleton it replaces.
        self._lock = threading.Lock()

    @property
    def bundle_name(self) -> str:
        return self._name

    @property
    def repository_names(self) -> Tuple[str, ...]:
        """The repositories this bundle carries, in declaration order."""
        return self._names

    @property
    def tables(self) -> Tuple[str, ...]:
        """The DynamoDB table suffixes this bundle can reach, sorted.

        This is the function's data surface, and it is what a Terraform IAM
        policy for the domain has to cover.
        """
        return tuple(sorted({REPOSITORY_SPECS[name].table for name in self._names}))

    def __getattr__(self, item: str) -> Any:
        # Only called for names that are not in `__slots__` and not a property,
        # so every repository access lands here exactly once per attribute per
        # process and is served from `_built` after that.
        if item not in self._names:
            raise RepositoryNotInBundle(self._name, item)
        try:
            return self._built[item]
        except KeyError:
            pass
        with self._lock:
            if item not in self._built:
                self._built[item] = REPOSITORY_SPECS[item].build()
            return self._built[item]

    def __dir__(self) -> "list[str]":
        return sorted(set(super().__dir__()) | set(self._names))

    def __repr__(self) -> str:
        built = sorted(self._built)
        return f"<RepositoryBundle {self._name!r} carries={len(self._names)} built={built}>"

    if TYPE_CHECKING:  # pragma: no cover - typing only
        # Declared for type checkers only. At runtime these resolve through
        # `__getattr__`, which is what makes an out-of-domain access raise
        # rather than return a repository the function has no grant for.
        users: "UserRepository"
        oauth_accounts: "OAuthAccountRepository"
        webauthn_credentials: "WebAuthnCredentialRepository"
        car_makes: "CarMakeRepository"
        car_models: "CarModelRepository"
        car_generations: "CarGenerationRepository"
        categories: "CategoryRepository"
        part_manufacturers: "PartManufacturerRepository"
        retailers: "RetailerRepository"
        parts: "PartRepository"
        part_cars: "PartCarRepository"
        part_listings: "PartListingRepository"
        part_price_history: "PartPriceHistoryRepository"
        build_lists: "BuildListRepository"
        build_list_parts: "BuildListPartRepository"
        build_list_phases: "BuildListPhaseRepository"
        build_list_labor_estimates: "BuildListLaborEstimateRepository"
        build_logs: "BuildLogRepository"
        build_log_posts: "BuildLogPostRepository"
        votes: "VoteRepository"
        reports: "ReportRepository"
        bug_reports: "BugReportRepository"
        app_settings: "AppSettingsRepository"
        part_price_alerts: "PartPriceAlertRepository"
        image_source_mappings: "ImageSourceMappingRepository"


#: The name every route already annotates with. It is the bundle; the alias
#: exists so that two hundred call sites did not have to change to say so.
Repositories = RepositoryBundle


_default: Optional[RepositoryBundle] = None
_default_lock = threading.Lock()


def build_bundle(names: Iterable[str], *, name: str = "all") -> RepositoryBundle:
    """A bundle carrying exactly `names`, building nothing yet."""
    return RepositoryBundle(names, name=name)


def get_repositories() -> RepositoryBundle:
    """The process default bundle: all twenty-five, built on first access.

    This is the dependency two hundred routes name, but a route serving a
    request almost never reaches this body. `bind_repositories` puts the
    application's own bundle in `dependency_overrides`, so FastAPI resolves
    `Depends(get_repositories)` to that bundle instead, and only a caller
    outside a request reaches the default here: `scripts/`, `init_cars`,
    `init_categories`, `car_inference`, and any test that touches a repository
    without going through an application.

    Making the default the full twenty-five rather than an error is what keeps
    those callers working unchanged. It is not what a deployed function serves,
    because every deployed function is built by a composition root and every
    composition root binds. `tests/entrypoints/test_repository_bundles.py`
    asserts the binding rather than trusting it.
    """
    global _default
    if _default is None:
        with _default_lock:
            if _default is None:
                _default = RepositoryBundle(ALL_REPOSITORY_NAMES, name="all")
    return _default


def bind_repositories(app: "Any", bundle: RepositoryBundle) -> RepositoryBundle:
    """Make `app` resolve `Depends(get_repositories)` to `bundle`.

    Per application rather than per process, and that distinction is the whole
    reason this is an override rather than a module-level global. The route
    contract test builds all nine Root B applications in one interpreter, and a
    process global would leave whichever was built last installed for every test
    after it: `media`'s five repositories would become the whole suite's, and
    roughly ninety tests would fail somewhere unrelated to what they assert.
    Binding to the application keeps nine bundles alive side by side and lets a
    test build one without disturbing the others.

    A deployed function builds exactly one application, so in production this is
    the same thing as a process-wide bundle, reached the same way on every
    request.
    """
    app.dependency_overrides[get_repositories] = lambda: bundle
    return bundle


def reset_default_repositories() -> None:
    """Drop the memoised process default. For tests that assert laziness."""
    global _default
    with _default_lock:
        _default = None


__all__ = [
    "ALL_REPOSITORY_NAMES",
    "RepositoryBundle",
    "RepositoryNotInBundle",
    "Repositories",
    "bind_repositories",
    "build_bundle",
    "get_repositories",
    "reset_default_repositories",
]
