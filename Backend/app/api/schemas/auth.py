from pydantic import BaseModel


class NewPassword(BaseModel):
    password: str
