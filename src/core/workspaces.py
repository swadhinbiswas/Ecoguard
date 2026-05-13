"""Multi-tenancy: workspaces, teams, roles, and resource scoping."""

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import Base


class WorkspaceRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), unique=True, index=True, nullable=False)
    slug = Column(String(128), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by = Column(String, nullable=True)
    settings = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), nullable=False, index=True
    )
    username = Column(String(128), nullable=False, index=True)
    role = Column(SAEnum(WorkspaceRole), default=WorkspaceRole.MEMBER, nullable=False)
    joined_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class WorkspaceAPIKey(Base):
    __tablename__ = "workspace_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), nullable=False, index=True
    )
    key_hash = Column(String(128), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    scopes = Column(JSON, default=list)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class TokenQuota(Base):
    __tablename__ = "token_quotas"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id"), nullable=False, index=True
    )
    period = Column(String(16), default="monthly")  # daily, weekly, monthly
    max_tokens = Column(Integer, nullable=False)
    current_tokens = Column(Integer, default=0)
    reset_at = Column(DateTime(timezone=True), nullable=False)


# ── Workspace Service ──────────────────────────────────────────


class WorkspaceService:
    @staticmethod
    async def create_workspace(
        db: AsyncSession,
        name: str,
        slug: str,
        created_by: str,
        description: str = "",
    ) -> Workspace:
        ws = Workspace(
            name=name, slug=slug, created_by=created_by, description=description
        )
        db.add(ws)
        await db.flush()

        member = WorkspaceMember(
            workspace_id=ws.id,
            username=created_by,
            role=WorkspaceRole.OWNER,
        )
        db.add(member)
        await db.flush()
        return ws

    @staticmethod
    async def get_workspace(db: AsyncSession, slug: str) -> Optional[Workspace]:
        result = await db.execute(
            select(Workspace).where(Workspace.slug == slug, Workspace.is_active)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_workspaces(db: AsyncSession, username: str) -> list[Workspace]:
        result = await db.execute(
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                WorkspaceMember.username == username,
                Workspace.is_active,
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_member_role(
        db: AsyncSession, workspace_id: int, username: str
    ) -> Optional[WorkspaceRole]:
        result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.username == username,
            )
        )
        member = result.scalar_one_or_none()
        return member.role if member else None

    @staticmethod
    async def add_member(
        db: AsyncSession,
        workspace_slug: str,
        username: str,
        role: WorkspaceRole = WorkspaceRole.MEMBER,
    ) -> WorkspaceMember:
        ws = await WorkspaceService.get_workspace(db, workspace_slug)
        if not ws:
            raise ValueError(f"Workspace {workspace_slug} not found")

        existing = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws.id,
                WorkspaceMember.username == username,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"User {username} already in workspace")

        member = WorkspaceMember(workspace_id=ws.id, username=username, role=role)
        db.add(member)
        await db.flush()
        return member

    @staticmethod
    async def check_quota(
        db: AsyncSession, workspace_id: int, requested_tokens: int
    ) -> tuple[bool, str]:
        result = await db.execute(
            select(TokenQuota).where(TokenQuota.workspace_id == workspace_id)
        )
        quota = result.scalar_one_or_none()
        if not quota:
            return True, ""

        now = datetime.now(timezone.utc)
        if now >= quota.reset_at:
            quota.current_tokens = 0
            from datetime import timedelta

            period_map = {"daily": 1, "weekly": 7, "monthly": 30}
            days = period_map.get(quota.period, 30)
            quota.reset_at = now + timedelta(days=days)

        if quota.current_tokens + requested_tokens > quota.max_tokens:
            remaining = quota.max_tokens - quota.current_tokens
            return (
                False,
                f"Token quota exceeded ({remaining} remaining of {quota.max_tokens})",
            )

        quota.current_tokens += requested_tokens
        await db.flush()
        return True, ""

    @staticmethod
    async def set_quota(
        db: AsyncSession,
        workspace_id: int,
        max_tokens: int,
        period: str = "monthly",
    ) -> TokenQuota:
        result = await db.execute(
            select(TokenQuota).where(TokenQuota.workspace_id == workspace_id)
        )
        quota = result.scalar_one_or_none()

        from datetime import timedelta

        period_map = {"daily": 1, "weekly": 7, "monthly": 30}
        days = period_map.get(period, 30)
        reset_at = datetime.now(timezone.utc) + timedelta(days=days)

        if quota:
            quota.max_tokens = max_tokens
            quota.period = period
            quota.reset_at = reset_at
            quota.current_tokens = 0
        else:
            quota = TokenQuota(
                workspace_id=workspace_id,
                max_tokens=max_tokens,
                period=period,
                reset_at=reset_at,
                current_tokens=0,
            )
            db.add(quota)

        await db.flush()
        return quota
