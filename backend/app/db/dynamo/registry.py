"""One name per repository, and the table each one owns.

This is the catalogue the bundles are cut from. It exists so that "which
repositories does `media` need" and "which tables does `media` therefore touch"
are answered from one table rather than from two lists that drift.

Every entry is a factory, never an instance. Importing this module must
construct no repository and reach no DynamoDB client, because
`app.composition.domains` imports it to declare each domain's bundle and that
import happens in every one of the nine functions. The factory's module is
recorded alongside it and imported only when a bundle actually builds the
repository, which is what keeps `app.entrypoints.media` from importing
`app.db.dynamo.build_lists` at all.

The `table` value is `TableSpec.suffix`, the same string section 1.2 of
`docs/migration/split-plan.md` uses in its ownership table and the same one
`app.db.dynamo.client.table_name` prefixes with the environment to get the real
DynamoDB table name. `tests/entrypoints/test_repository_bundles.py` compares the
two, so a repository added here without a plan row, or a plan row without a
repository, fails rather than being noticed later in an IAM policy.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Tuple

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.db.dynamo.repository import DynamoRepository


@dataclass(frozen=True)
class RepositorySpec:
    """Where a repository's class lives, and which table it owns.

    `module` and `class_name` are strings rather than the class itself so that
    reading this catalogue costs no import. `build()` is the only thing that
    imports, and a bundle calls it once per repository it declares.
    """

    #: The attribute name on the bundle: `repos.<name>`.
    name: str
    #: Dotted module path under `app.db.dynamo`.
    module: str
    #: The repository class in that module.
    class_name: str
    #: `TableSpec.suffix`, matching the plan's table names.
    table: str

    def build(self) -> "DynamoRepository[Any]":
        """Import the defining module and construct the repository."""
        module = importlib.import_module(f"app.db.dynamo.{self.module}")
        return getattr(module, self.class_name)()  # type: ignore[no-any-return]


def _spec(name: str, module: str, class_name: str, table: str) -> Tuple[str, RepositorySpec]:
    return name, RepositorySpec(name=name, module=module, class_name=class_name, table=table)


#: The twenty-five repositories, keyed by the attribute name routes already use.
#: The order is the order the old frozen dataclass declared its fields in, so
#: the diff against it reads as a move.
REPOSITORY_SPECS: Dict[str, RepositorySpec] = dict(
    [
        _spec("users", "users", "UserRepository", "users"),
        _spec("oauth_accounts", "users", "OAuthAccountRepository", "oauth_accounts"),
        _spec("webauthn_credentials", "users", "WebAuthnCredentialRepository", "webauthn_credentials"),
        _spec("car_makes", "catalog", "CarMakeRepository", "car_makes"),
        _spec("car_models", "catalog", "CarModelRepository", "car_models"),
        _spec("car_generations", "catalog", "CarGenerationRepository", "car_generations"),
        _spec("categories", "catalog", "CategoryRepository", "categories"),
        _spec("part_manufacturers", "catalog", "PartManufacturerRepository", "part_manufacturers"),
        _spec("retailers", "catalog", "RetailerRepository", "retailers"),
        _spec("parts", "catalog", "PartRepository", "parts"),
        _spec("part_cars", "catalog", "PartCarRepository", "part_cars"),
        _spec("part_listings", "catalog", "PartListingRepository", "part_listings"),
        _spec("part_price_history", "catalog", "PartPriceHistoryRepository", "part_price_history"),
        _spec("build_lists", "build_lists", "BuildListRepository", "build_lists"),
        _spec("build_list_parts", "build_lists", "BuildListPartRepository", "build_list_parts"),
        _spec("build_list_phases", "build_lists", "BuildListPhaseRepository", "build_list_phases"),
        _spec(
            "build_list_labor_estimates",
            "build_lists",
            "BuildListLaborEstimateRepository",
            "build_list_labor_estimates",
        ),
        _spec("build_logs", "build_logs", "BuildLogRepository", "build_logs"),
        _spec("build_log_posts", "build_logs", "BuildLogPostRepository", "build_log_posts"),
        _spec("votes", "moderation", "VoteRepository", "votes"),
        _spec("reports", "moderation", "ReportRepository", "reports"),
        _spec("bug_reports", "bug_reports", "BugReportRepository", "bug_reports"),
        _spec("app_settings", "app_settings", "AppSettingsRepository", "app_settings"),
        _spec("part_price_alerts", "part_price_alerts", "PartPriceAlertRepository", "part_price_alerts"),
        _spec(
            "image_source_mappings",
            "image_source_mappings",
            "ImageSourceMappingRepository",
            "image_source_mappings",
        ),
    ]
)

#: All twenty-five names. Root A's bundle, and the upper bound on any domain's.
ALL_REPOSITORY_NAMES: Tuple[str, ...] = tuple(REPOSITORY_SPECS)


def tables_for(names: "Tuple[str, ...]") -> Tuple[str, ...]:
    """The table suffixes a set of repository names touches, sorted.

    Used by the bundle tests and by anything that wants to state a function's
    DynamoDB surface without constructing a repository to ask it.
    """
    return tuple(sorted({REPOSITORY_SPECS[name].table for name in names}))
