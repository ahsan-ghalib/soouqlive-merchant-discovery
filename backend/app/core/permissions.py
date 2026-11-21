"""Role-based access control helpers."""

from enum import Enum
from typing import Iterable


class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


ROLE_HIERARCHY: dict[Role, int] = {
    Role.VIEWER: 1,
    Role.RESEARCHER: 2,
    Role.MANAGER: 3,
    Role.ADMIN: 4,
}


def has_minimum_role(user_role: str, required: Role) -> bool:
    try:
        current = Role(user_role)
    except ValueError:
        return False
    return ROLE_HIERARCHY[current] >= ROLE_HIERARCHY[required]


def has_any_role(user_role: str, allowed: Iterable[str | Role]) -> bool:
    allowed_values = {str(r) for r in allowed}
    return user_role in allowed_values
