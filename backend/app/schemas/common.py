from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: str | None = None


class MessageResponse(BaseModel):
    message: str
