from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.part import Part as DBPart
from app.api.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.db.session import get_db

router = APIRouter()


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    db: Session = Depends(get_db),
) -> List[DBCategory]:
    """
    Get all active categories.
    """
    categories = (
        db.query(DBCategory)
        .filter(DBCategory.is_active == True)
        .order_by(DBCategory.sort_order)
        .all()
    )
    return categories


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    db: Session = Depends(get_db),
) -> DBCategory:
    """
    Get specific category details.
    """
    category = db.query(DBCategory).filter(DBCategory.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )
    return category


@router.get("/{category_id}/parts", response_model=List[Any])
async def get_parts_by_category(
    category_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> List[DBPart]:
    """
    Get parts by category with pagination.
    """
    # First verify the category exists
    category = db.query(DBCategory).filter(DBCategory.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    parts = (
        db.query(DBPart)
        .filter(DBPart.category_id == category_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return parts


@router.post("/", response_model=CategoryResponse)
async def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
) -> DBCategory:
    """
    Create a new category (admin only).
    """
    # Check if category with same name already exists
    existing_category = (
        db.query(DBCategory).filter(DBCategory.name == category.name).first()
    )
    if existing_category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists",
        )

    db_category = DBCategory(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category: CategoryUpdate,
    db: Session = Depends(get_db),
) -> DBCategory:
    """
    Update a category (admin only).
    """
    db_category = db.query(DBCategory).filter(DBCategory.id == category_id).first()
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    update_data = category.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)

    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Delete a category (admin only).
    """
    db_category = db.query(DBCategory).filter(DBCategory.id == category_id).first()
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    # Check if there are any parts using this category
    parts_count = db.query(DBPart).filter(DBPart.category_id == category_id).count()
    if parts_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete category: {parts_count} parts are using this category",
        )

    db.delete(db_category)
    db.commit()
    return {"message": "Category deleted successfully"}
