from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


# Schema for request body when creating a user
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


# Schema for request body when updating a user
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    disabled: Optional[bool] = None
    password: Optional[str] = None
    image_url: Optional[str] = None
    current_password: str


# Schema for admin operations when updating a user
class AdminUserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    disabled: Optional[bool] = None
    password: Optional[str] = None
    image_url: Optional[str] = None
    is_superuser: Optional[bool] = None
    is_admin: Optional[bool] = None
    email_verified: Optional[bool] = None


# Schema for response body when reading a user (DO NOT include hashed password)
class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    disabled: bool
    email_verified: bool
    image_url: Optional[str] = None
    is_superuser: bool
    is_admin: bool

    model_config = ConfigDict(from_attributes=True)
