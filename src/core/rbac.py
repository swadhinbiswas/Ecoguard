from enum import Enum

from fastapi import HTTPException, Request


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


ROLE_PERMISSIONS = {
    Role.ADMIN: {"read", "write", "delete", "admin"},
    Role.OPERATOR: {"read", "write"},
    Role.VIEWER: {"read"},
}

PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/metrics",
    "/api/v1/health",
    "/api/v1/ready",
    "/ws/metrics",
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
    role_header = request.headers.get("X-Role", "viewer")
    try:
        return Role(role_header.lower())
    except ValueError:
        return Role.VIEWER


async def require_role(required: str, request: Request) -> None:
    if request.url.path in PUBLIC_PATHS:
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
