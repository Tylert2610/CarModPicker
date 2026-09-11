"""Generic CRUD service over a DynamoDB repository."""

from typing import Any, Dict, Generic, Optional, TypeVar
from uuid import UUID

from fastapi import HTTPException, status

from app.api.protocols import HasModelDump
from app.db.dynamo.errors import ItemNotFound
from app.db.dynamo.models import DynamoModel
from app.db.dynamo.repository import DynamoRepository, Page
from app.db.dynamo.users import User as DBUser

TModel = TypeVar("TModel", bound=DynamoModel)
TCreate = TypeVar("TCreate", bound=HasModelDump)
TUpdate = TypeVar("TUpdate", bound=HasModelDump)


class BaseDynamoCRUDService(Generic[TModel, TCreate, TUpdate]):
    """CRUD operations plus ownership checks for one entity type."""

    def __init__(self, repository: DynamoRepository[TModel], entity_name: str) -> None:
        """Bind the service to a repository and the entity name used in errors."""
        self.repository = repository
        self.entity_name = entity_name

    def not_found(self) -> HTTPException:
        """Return the 404 raised when the entity does not exist."""
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{self.entity_name.title()} not found")

    def forbidden(self, action: str = "access") -> HTTPException:
        """Return the 403 raised when the caller may not perform an action."""
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Not authorized to {action} this {self.entity_name}"
        )

    def owner_id(self, entity: TModel) -> Optional[UUID]:
        """Return the entity's owner id, or None when it has no owner."""
        owner = getattr(entity, "user_id", None)
        return owner if isinstance(owner, UUID) else None

    def can_modify(self, entity: TModel, current_user: DBUser) -> bool:
        """Report whether the user owns the entity or is an admin."""
        owner = self.owner_id(entity)
        return owner is None or owner == current_user.id or current_user.is_admin or current_user.is_superuser

    def get_by_id(
        self,
        entity_id: UUID,
        current_user: Optional[DBUser] = None,
        allow_public: bool = False,
    ) -> TModel:
        """Fetch an entity, enforcing ownership unless public access is allowed."""
        try:
            entity = self.repository.get_or_raise(entity_id)
        except ItemNotFound:
            raise self.not_found()
        if not allow_public:
            if current_user is None or not self.can_modify(entity, current_user):
                raise self.forbidden()
        return entity

    def build_entity(self, data: TCreate, current_user: DBUser, additional_data: Optional[Dict[str, Any]]) -> TModel:
        """Build a model instance from create input, stamping the owner."""
        payload = data.model_dump()
        if additional_data:
            payload.update(additional_data)
        if "user_id" in self.repository.model_cls.model_fields:
            payload["user_id"] = current_user.id
        return self.repository.model_cls.model_validate(payload)

    def create(self, data: TCreate, current_user: DBUser, additional_data: Optional[Dict[str, Any]] = None) -> TModel:
        """Persist a new entity owned by the current user."""
        return self.repository.create(self.build_entity(data, current_user, additional_data))

    def apply_update(self, entity: TModel, changes: Dict[str, Any]) -> TModel:
        """Persist an entity with the given field changes applied."""
        return self.repository.put(entity.model_copy(update=changes))

    def update(self, entity_id: UUID, data: TUpdate, current_user: DBUser) -> TModel:
        """Apply an update to an entity the caller is allowed to modify."""
        entity = self.get_by_id(entity_id, allow_public=True)
        if not self.can_modify(entity, current_user):
            raise self.forbidden("update")
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return entity
        if "updated_at" in self.repository.model_cls.model_fields:
            from app.db.dynamo.models import utc_now

            changes["updated_at"] = utc_now()
        return self.apply_update(entity, changes)

    def delete(self, entity_id: UUID, current_user: DBUser) -> TModel:
        """Delete an entity the caller is allowed to modify and return it."""
        entity = self.get_by_id(entity_id, allow_public=True)
        if not self.can_modify(entity, current_user):
            raise self.forbidden("delete")
        self.repository.delete(entity_id)
        return entity

    def list_page(self, *, limit: int, cursor: Optional[str]) -> Page[TModel]:
        """Return one page of entities."""
        return self.repository.scan(limit=limit, cursor=cursor)

    def list_by_parent(
        self,
        index: str,
        key_value: Any,
        *,
        limit: int,
        cursor: Optional[str],
        scan_forward: bool = True,
    ) -> Page[TModel]:
        """Return one page of entities from an index keyed by a parent."""
        return self.repository.query(index, key_value, limit=limit, cursor=cursor, scan_forward=scan_forward)

    def count(self) -> int:
        """Return the total number of stored entities."""
        return len(self.repository.scan_all())
