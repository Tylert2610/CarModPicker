"""
CarGeneration service that extends BaseDynamoCRUDService to eliminate redundancy.
"""

import logging
from typing import Callable, Iterable, Optional
from uuid import UUID

from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.schemas.car_generation import CarGenerationCreate, CarGenerationRead, CarGenerationUpdate
from app.api.schemas.pagination import CursorPage
from app.api.services.base_dynamo_crud_service import BaseDynamoCRUDService
from app.db.dynamo import search
from app.db.dynamo.catalog import CarGeneration, CarMake, CarModel


class CarGenerationService(BaseDynamoCRUDService[CarGeneration, CarGenerationCreate, CarGenerationUpdate]):
    """
    CarGeneration service that provides read operations for car generations.

    car_make/car_model names are resolved through the CarModel and CarMake repositories.
    """

    def __init__(self, repos: Optional[Repositories] = None) -> None:
        """Bind the service to a repository bundle."""
        self.repos = repos or get_repositories()
        super().__init__(repository=self.repos.car_generations, entity_name="car_generation")

    def _models_and_makes(
        self, generations: Iterable[CarGeneration]
    ) -> tuple[dict[UUID, CarModel], dict[UUID, CarMake]]:
        """Load the car models and makes these generations refer to."""
        models = self.repos.car_models.get_many({gen.car_model_id for gen in generations})
        makes = self.repos.car_makes.get_many({model.car_make_id for model in models.values()})
        return models, makes

    def hydrate(self, generations: Iterable[CarGeneration]) -> list[CarGenerationRead]:
        """Resolve make and model names onto many generations."""
        items = list(generations)
        models, makes = self._models_and_makes(items)
        return [self._to_read(gen, models, makes) for gen in items]

    def hydrate_one(self, generation: CarGeneration) -> CarGenerationRead:
        """Resolve make and model names onto a single generation."""
        return self.hydrate([generation])[0]

    @staticmethod
    def _to_read(gen: CarGeneration, models: dict[UUID, CarModel], makes: dict[UUID, CarMake]) -> CarGenerationRead:
        """Build a read schema from a generation and its resolved model and make."""
        model = models.get(gen.car_model_id)
        make = makes.get(model.car_make_id) if model is not None else None
        return CarGenerationRead(
            id=gen.id,
            car_make_name=make.name if make is not None else "",
            car_model_name=model.name if model is not None else "",
            car_model_display_name=model.display_name if model is not None else None,
            generation_name=gen.generation_name,
            display_name=gen.display_name,
            start_year=gen.start_year,
            end_year=gen.end_year,
            description=gen.description,
            image_urls=gen.image_urls,
        )

    def get_read(self, entity_id: UUID, logger: Optional[logging.Logger] = None) -> CarGenerationRead:
        """Fetch one generation with its make and model names resolved."""
        gen = self.get_by_id(entity_id, allow_public=True)
        if logger:
            logger.info(f"Retrieved {self.entity_name} {entity_id}")
        return self.hydrate_one(gen)

    def get_by_ids(self, ids: list[UUID], logger: Optional[logging.Logger] = None) -> list[CarGenerationRead]:
        """Return car generations whose IDs are in the provided list."""
        if not ids:
            return []
        found = self.repos.car_generations.get_many(ids)
        ordered = [found[gen_id] for gen_id in dict.fromkeys(ids) if gen_id in found]
        if logger:
            logger.info(f"Retrieved {len(ordered)} car_generations by ID batch")
        return self.hydrate(ordered)

    def _paginate(
        self,
        generations: list[CarGeneration],
        *,
        limit: int,
        cursor: str | None,
        sort_key: Callable[[CarGeneration], str] | None = None,
    ) -> CursorPage[CarGenerationRead]:
        """Paginate generations, hydrating each page in one lookup."""
        models, makes = self._models_and_makes(generations)
        return search.paginate(
            generations,
            limit=limit,
            cursor=cursor,
            sort_key=sort_key or (lambda gen: search.datetime_key(gen.created_at, descending=True)),
            transform=lambda gen: self._to_read(gen, models, makes),
        )

    def list_page_read(self, *, limit: int, cursor: str | None) -> CursorPage[CarGenerationRead]:
        """Return one page of generations, newest first."""
        return self._paginate(self.repos.car_generations.list_all(), limit=limit, cursor=cursor)

    def _generations_for_models(self, models: Iterable[CarModel]) -> list[CarGeneration]:
        """Collect every generation belonging to these models."""
        generations: list[CarGeneration] = []
        for model in models:
            generations.extend(self.repos.car_generations.list_by_model(model.id))
        return generations

    def get_car_generations_by_make_model(
        self,
        car_make_name: str,
        car_model_name: Optional[str] = None,
        *,
        limit: int,
        cursor: str | None,
        logger: Optional[logging.Logger] = None,
    ) -> CursorPage[CarGenerationRead]:
        """
        Get car generations filtered by car_make and/or car_model.
        """
        make = self.repos.car_makes.get_by_name(car_make_name)
        generations: list[CarGeneration] = []
        if make is not None and make.name == car_make_name:
            if car_model_name is not None:
                model = self.repos.car_models.get_by_make_and_name(make.id, car_model_name)
                models = [model] if model is not None and model.name == car_model_name else []
            else:
                models = self.repos.car_models.list_by_make(make.id)
            generations = self._generations_for_models(models)
        if logger:
            logger.info(f"Retrieved {len(generations)} car_generations by car_make/car_model")
        return self._paginate(generations, limit=limit, cursor=cursor)

    def search_car_generations(
        self,
        search_term: str,
        *,
        limit: int,
        cursor: str | None,
        logger: Optional[logging.Logger] = None,
    ) -> CursorPage[CarGenerationRead]:
        """
        Search car generations by car_make, car_model, or generation name.
        """
        generations = self.matching_generations(search_term)
        if logger:
            logger.info(f"Retrieved {len(generations)} car_generations for search")
        return self._paginate(generations, limit=limit, cursor=cursor)

    def matching_generations(self, search_term: str, *, include_years: bool = False) -> list[CarGeneration]:
        """Return generations matching a search term across make, model and name."""
        term = search.normalize_term(search_term)
        matching_make_ids = {make.id for make in self.repos.car_makes.list_all() if search.contains(term, make.name)}
        models = self.repos.car_models.list_all()
        matching_model_ids = {
            model.id for model in models if model.car_make_id in matching_make_ids or search.contains(term, model.name)
        }

        def matches(gen: CarGeneration) -> bool:
            """Report whether this generation matches the search term."""
            if gen.car_model_id in matching_model_ids or search.contains(term, gen.generation_name):
                return True
            return include_years and search.contains(term, str(gen.start_year), str(gen.end_year or ""))

        return search.scan_matching(self.repos.car_generations, matches)

    def count_by_make(self) -> dict[str, int]:
        """Return the number of generations per make name."""
        models = {model.id: model for model in self.repos.car_models.list_all()}
        makes = self.repos.car_makes.get_many({model.car_make_id for model in models.values()})
        counts: dict[str, int] = {}
        for gen in self.repos.car_generations.list_all():
            model = models.get(gen.car_model_id)
            make = makes.get(model.car_make_id) if model is not None else None
            if make is None:
                continue
            counts[make.name] = counts.get(make.name, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
