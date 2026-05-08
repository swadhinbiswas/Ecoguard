from enum import Enum

from fastapi import HTTPException, Request

from src.core.auth import is_public_path


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


ROLE_PERMISSIONS = {
    Role.ADMIN: {"read", "write", "delete", "admin"},
    Role.OPERATOR: {"read", "write"},
    Role.VIEWER: {"read"},
}

DASHBOARD_VIEWER_PATHS = {"/dashboard", "/dashboard/"}
DASHBOARD_PATHS = {
    "/dashboard/models",
    "/dashboard/inference",
    "/dashboard/drift",
    "/dashboard/experiments",
    "/dashboard/jobs",
    "/dashboard/datasets",
}


async def get_current_role(request: Request) -> Role:
    user = getattr(request.state, "user", None) or {}
    role_value = user.get("role", "viewer")
    try:
        return Role(str(role_value).lower())
    except ValueError:
        return Role.VIEWER


async def require_role(required: str, request: Request) -> None:
    if is_public_path(request.url.path):
        return

    role = await get_current_role(request)

    if required == "read":
        if role not in (Role.VIEWER, Role.OPERATOR, Role.ADMIN):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    elif required == "write":
        if role not in (Role.OPERATOR, Role.ADMIN):
            raise HTTPException(status_code=403, detail="Write access required")
    elif required == "admin":
        if role != Role.ADMIN:
            raise HTTPException(status_code=403, detail="Admin access required")
