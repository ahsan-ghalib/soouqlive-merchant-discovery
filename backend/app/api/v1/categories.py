"""Business category endpoints (foundation)."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.category import BusinessCategory
from app.utils.pagination import success_response

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("")
async def list_categories(db: DbSession, _user: CurrentUser):
    result = await db.execute(
        select(BusinessCategory)
        .where(BusinessCategory.is_active.is_(True))
        .order_by(BusinessCategory.name)
    )
    categories = result.scalars().all()
    data = [
        {
            "id": str(c.id),
            "parent_id": str(c.parent_id) if c.parent_id else None,
            "name": c.name,
            "name_ar": c.name_ar,
            "slug": c.slug,
            "description": c.description,
        }
        for c in categories
    ]
    return success_response(data=data, message="Categories retrieved")


@router.get("/tree")
async def category_tree(db: DbSession, _user: CurrentUser):
    result = await db.execute(
        select(BusinessCategory).where(BusinessCategory.is_active.is_(True))
    )
    categories = list(result.scalars().all())
    by_parent: dict[str | None, list] = {}
    for c in categories:
        key = str(c.parent_id) if c.parent_id else None
        by_parent.setdefault(key, []).append(c)

    def build(parent_key: str | None) -> list[dict]:
        nodes = []
        for c in by_parent.get(parent_key, []):
            nodes.append(
                {
                    "id": str(c.id),
                    "name": c.name,
                    "name_ar": c.name_ar,
                    "slug": c.slug,
                    "children": build(str(c.id)),
                }
            )
        return nodes

    return success_response(data=build(None), message="Category tree retrieved")
