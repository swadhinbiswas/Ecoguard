from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    desc,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    template = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PromptTemplateService:
    @staticmethod
    async def create(
        db: AsyncSession,
        name: str,
        template: str,
        description: str | None = None,
        variables: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> PromptTemplate:
        entry = PromptTemplate(
            name=name,
            template=template,
            description=description,
            variables=variables or [],
            tags=tags or [],
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def list_templates(
        db: AsyncSession,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PromptTemplate]:
        q = select(PromptTemplate).order_by(desc(PromptTemplate.updated_at))
        if tag:
            q = q.where(PromptTemplate.tags.contains([tag]))
        result = await db.execute(q.offset(offset).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def get_template(db: AsyncSession, template_id: int) -> PromptTemplate | None:
        result = await db.execute(
            select(PromptTemplate).where(PromptTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def render(
        db: AsyncSession,
        template_id: int,
        variables: dict[str, str],
    ) -> Optional[str]:
        tmpl = await PromptTemplateService.get_template(db, template_id)
        if not tmpl:
            return None

        rendered = tmpl.template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)

        tmpl.usage_count += 1
        tmpl.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return rendered

    @staticmethod
    async def delete(db: AsyncSession, template_id: int) -> bool:
        tmpl = await PromptTemplateService.get_template(db, template_id)
        if not tmpl:
            return False
        await db.delete(tmpl)
        await db.flush()
        return True
