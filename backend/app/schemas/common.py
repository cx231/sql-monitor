from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: dict[str, object] | None = None


class ApiResponse(BaseModel, Generic[T]):
    data: T | None = None
    error: ErrorBody | None = None
