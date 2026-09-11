from typing import Any, Callable, Dict, Generic, List, Optional, Sequence, Type, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel as PydanticModel

from app.api.dependencies.auth import get_current_user
from app.api.protocols import HasModelDump
from app.api.schemas.pagination import CursorPage
from app.api.services.base_dynamo_crud_service import BaseDynamoCRUDService
from app.api.utils.cursor_pagination import CursorParams, get_cursor_params
from app.db.dynamo.models import DynamoModel
from app.db.dynamo.users import User as DBUser

TModel = TypeVar("TModel", bound=DynamoModel)
CreateSchema = TypeVar("CreateSchema", bound=HasModelDump)
ReadSchema = TypeVar("ReadSchema", bound=PydanticModel)
UpdateSchema = TypeVar("UpdateSchema", bound=HasModelDump)


class BaseDynamoEndpointRouter(Generic[TModel, CreateSchema, ReadSchema, UpdateSchema]):
    def __init__(
        self,
        service: BaseDynamoCRUDService[TModel, CreateSchema, UpdateSchema],
        router: APIRouter,
        entity_name: str,
        *,
        read_schema: Type[ReadSchema],
        create_schema: Optional[Type[CreateSchema]] = None,
        update_schema: Optional[Type[UpdateSchema]] = None,
        allow_public_read: bool = False,
        additional_create_data: Optional[Dict[str, Any]] = None,
        disable_endpoints: Optional[List[str]] = None,
        serialize: Optional[Callable[[TModel], Any]] = None,
        serialize_many: Optional[Callable[[Sequence[TModel]], List[Any]]] = None,
    ) -> None:
        self.service = service
        self.router = router
        self.entity_name = entity_name
        self.allow_public_read = allow_public_read
        self.additional_create_data = additional_create_data or {}
        self.disabled = set(disable_endpoints or [])
        self._read_schema = read_schema
        self._create_schema = create_schema
        self._update_schema = update_schema
        self._serialize = serialize or read_schema.model_validate
        self._serialize_many = serialize_many or (lambda entities: [self._serialize(e) for e in entities])
        self._register_common_endpoints()

    def _register_common_endpoints(self) -> None:
        entity_name = self.entity_name
        read_schema = self._read_schema
        create_schema = self._create_schema
        update_schema = self._update_schema

        if "count" not in self.disabled:

            @self.router.get(
                "/count",
                response_model=Dict[str, int],
                responses={200: {"description": f"{entity_name.title()} count retrieved successfully"}},
            )
            async def count_entities() -> Dict[str, int]:  # pyright: ignore[reportUnusedFunction]
                return {"count": self.service.count()}

        if "create" not in self.disabled and create_schema is not None:

            @self.router.post(
                "",
                response_model=read_schema,
                responses={
                    400: {"description": "Bad request"},
                    403: {"description": "Not authorized"},
                    409: {"description": f"{entity_name.title()} already exists"},
                },
            )
            async def create_entity(  # pyright: ignore[reportUnusedFunction]
                data: create_schema,  # type: ignore[valid-type]
                current_user: DBUser = Depends(get_current_user),
            ) -> Any:
                entity = self.service.create(data, current_user, self.additional_create_data)
                return self._serialize(entity)

        if "get" not in self.disabled:
            if self.allow_public_read:

                @self.router.get(
                    "/{entity_id}",
                    response_model=read_schema,
                    responses={404: {"description": f"{entity_name.title()} not found"}},
                )
                async def read_entity_public(entity_id: UUID) -> Any:  # pyright: ignore[reportUnusedFunction]
                    return self._serialize(self.service.get_by_id(entity_id, allow_public=True))

            else:

                @self.router.get(
                    "/{entity_id}",
                    response_model=read_schema,
                    responses={
                        403: {"description": "Not authorized"},
                        404: {"description": f"{entity_name.title()} not found"},
                    },
                )
                async def read_entity(  # pyright: ignore[reportUnusedFunction]
                    entity_id: UUID,
                    current_user: DBUser = Depends(get_current_user),
                ) -> Any:
                    return self._serialize(self.service.get_by_id(entity_id, current_user=current_user))

        if "list" not in self.disabled:

            @self.router.get(
                "",
                response_model=CursorPage[read_schema],  # type: ignore[valid-type]
                responses={200: {"description": f"{entity_name.title()} page retrieved successfully"}},
            )
            async def list_entities(  # pyright: ignore[reportUnusedFunction]
                params: CursorParams = Depends(get_cursor_params),
            ) -> Any:
                page = self.service.list_page(limit=params.limit, cursor=params.cursor)
                return CursorPage(
                    items=self._serialize_many(page.items),
                    next_cursor=page.next_cursor,
                    has_next=page.next_cursor is not None,
                )

        if "update" not in self.disabled and update_schema is not None:

            @self.router.put(
                "/{entity_id}",
                response_model=read_schema,
                responses={
                    403: {"description": "Not authorized"},
                    404: {"description": f"{entity_name.title()} not found"},
                },
            )
            async def update_entity(  # pyright: ignore[reportUnusedFunction]
                entity_id: UUID,
                data: update_schema,  # type: ignore[valid-type]
                current_user: DBUser = Depends(get_current_user),
            ) -> Any:
                return self._serialize(self.service.update(entity_id, data, current_user))

        if "delete" not in self.disabled:

            @self.router.delete(
                "/{entity_id}",
                response_model=read_schema,
                responses={
                    403: {"description": "Not authorized"},
                    404: {"description": f"{entity_name.title()} not found"},
                },
            )
            async def delete_entity(  # pyright: ignore[reportUnusedFunction]
                entity_id: UUID,
                current_user: DBUser = Depends(get_current_user),
            ) -> Any:
                return self._serialize(self.service.delete(entity_id, current_user))
