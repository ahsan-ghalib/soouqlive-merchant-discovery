"""Pagination helpers."""

from typing import Any, Generic, Optional, Sequence, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int = 1
    limit: int = 20
    total: int = 0


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Operation completed"
    data: Optional[T] = None
    meta: Optional[PaginationMeta] = None


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def paginated_response(
    items: Sequence[Any],
    total: int,
    page: int,
    limit: int,
    message: str = "Operation completed",
) -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "data": items,
        "meta": {"page": page, "limit": limit, "total": total},
    }


def success_response(
    data: Any = None,
    message: str = "Operation completed",
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "data": data,
        "meta": meta,
    }


def error_response(
    message: str,
    data: Any = None,
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "message": message,
        "data": data,
        "meta": meta,
    }
