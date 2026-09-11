"""One name per repository, and the table each one owns.

Entries are factories, never instances, so importing this catalogue constructs
no repository and reaches no DynamoDB client. `table` is the `TableSpec.suffix`.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from app.db.dynamo.repository import DynamoRepository


@dataclass(frozen=True)
class RepositorySpec:
    """Where a repository's class lives, and which table it owns.

    `module` and `class_name` are strings so reading this catalogue costs no
    import; `build()` is the only thing that imports.
    """

    name: str
    module: str
    class_name: str
    table: str

    def build(self) -> "DynamoRepository[Any]":
        """Import the defining module and construct the repository."""
        module = importlib.import_module(f"app.db.dynamo.{self.module}")
        return getattr(module, self.class_name)()  # type: ignore[no-any-return]


def _spec(name: str, module: str, class_name: str, table: str) -> Tuple[str, RepositorySpec]:
    """Build one catalogue entry keyed by its repository name."""
    return name, RepositorySpec(name=name, module=module, class_name=class_name, table=table)


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

ALL_REPOSITORY_NAMES: Tuple[str, ...] = tuple(REPOSITORY_SPECS)


def tables_for(names: "Tuple[str, ...]") -> Tuple[str, ...]:
    """The table suffixes a set of repository names touches, sorted."""
    return tuple(sorted({REPOSITORY_SPECS[name].table for name in names}))
