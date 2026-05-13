"""Agent tracing: tree/DAG-based visualization for multi-step LLM agent calls."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import Base


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(64), unique=True, index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=True)
    parent_span_id = Column(String(64), nullable=True)
    span_id = Column(String(64), nullable=False, index=True)
    span_type = Column(
        String(32), nullable=False
    )  # llm_call, tool_call, retry, chain, agent
    name = Column(String(128), nullable=False)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    status = Column(String(16), default="running")  # running, success, error
    error_message = Column(Text, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Float, nullable=True)
    token_count = Column(Integer, nullable=True)
    model = Column(String(64), nullable=True)
    metadata_info = Column(JSON, nullable=True)


class AgentTracer:
    _active_traces: dict[str, list[AgentTrace]] = {}
    _lock = asyncio.Lock()

    @staticmethod
    async def start_trace(
        db: AsyncSession,
        session_id: str | None = None,
    ) -> str:
        trace_id = f"trace-{uuid.uuid4().hex[:12]}"
        await AgentTracer.start_span(
            db, trace_id, "agent", "agent-execution", session_id=session_id
        )
        return trace_id

    @staticmethod
    async def start_span(
        db: AsyncSession,
        trace_id: str,
        span_type: str,
        name: str,
        parent_span_id: str | None = None,
        input_data: dict | None = None,
        session_id: str | None = None,
        model: str | None = None,
    ) -> str:
        span_id = f"span-{uuid.uuid4().hex[:8]}"
        span = AgentTrace(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            span_type=span_type,
            name=name,
            input_data=input_data,
            status="running",
            start_time=datetime.now(timezone.utc),
            session_id=session_id,
            model=model,
        )
        db.add(span)
        await db.flush()
        return span_id

    @staticmethod
    async def end_span(
        db: AsyncSession,
        span_id: str,
        output_data: dict | None = None,
        error: str | None = None,
        token_count: int = 0,
    ) -> None:
        result = await db.execute(
            select(AgentTrace).where(AgentTrace.span_id == span_id)
        )
        span = result.scalar_one_or_none()
        if not span:
            return

        span.end_time = datetime.now(timezone.utc)
        span.duration_ms = (
            (span.end_time - span.start_time).total_seconds() * 1000
            if span.start_time
            else 0
        )
        span.output_data = output_data
        span.status = "error" if error else "success"
        span.error_message = error
        span.token_count = token_count
        await db.flush()

    @staticmethod
    async def trace_llm_call(
        db: AsyncSession,
        trace_id: str,
        parent_span_id: str,
        prompt: str,
        model: str,
        func: callable,
    ) -> dict:
        span_id = await AgentTracer.start_span(
            db,
            trace_id,
            "llm_call",
            f"LLM: {model}",
            parent_span_id=parent_span_id,
            input_data={"prompt": prompt[:500]},
            model=model,
        )

        try:
            result = await asyncio.to_thread(lambda: func())
            await AgentTracer.end_span(
                db,
                span_id,
                output_data={"output": str(result)[:500]},
                token_count=result.get("usage", {}).get("completion_tokens", 0)
                if isinstance(result, dict)
                else 0,
            )
            return result
        except Exception as e:
            await AgentTracer.end_span(db, span_id, error=str(e))
            raise

    @staticmethod
    async def trace_tool_call(
        db: AsyncSession,
        trace_id: str,
        parent_span_id: str,
        tool_name: str,
        tool_input: dict,
        func: callable,
    ) -> Any:
        span_id = await AgentTracer.start_span(
            db,
            trace_id,
            "tool_call",
            f"Tool: {tool_name}",
            parent_span_id=parent_span_id,
            input_data={"tool": tool_name, "input": tool_input},
        )

        try:
            result = func()
            if asyncio.iscoroutine(result):
                result = await result
            await AgentTracer.end_span(
                db,
                span_id,
                output_data={"output": str(result)[:1000]},
            )
            return result
        except Exception as e:
            await AgentTracer.end_span(db, span_id, error=str(e))
            raise

    @staticmethod
    async def get_trace_tree(db: AsyncSession, trace_id: str) -> dict[str, Any]:
        result = await db.execute(
            select(AgentTrace)
            .where(AgentTrace.trace_id == trace_id)
            .order_by(AgentTrace.start_time)
        )
        spans = result.scalars().all()

        span_map: dict[str, dict] = {}
        for span in spans:
            node = {
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "span_type": span.span_type,
                "name": span.name,
                "status": span.status,
                "duration_ms": span.duration_ms,
                "token_count": span.token_count,
                "model": span.model,
                "error": span.error_message,
                "start_time": span.start_time.isoformat() if span.start_time else None,
                "children": [],
            }
            span_map[span.span_id] = node

        root = None
        for span in spans:
            node = span_map[span.span_id]
            parent = span.parent_span_id
            if parent and parent in span_map:
                span_map[parent]["children"].append(node)
            elif not parent:
                root = node

        return {
            "trace_id": trace_id,
            "total_spans": len(spans),
            "total_duration_ms": sum(s.duration_ms or 0 for s in spans),
            "status": "success"
            if all(s.status == "success" for s in spans)
            else "error",
            "tree": root or span_map[spans[0].span_id] if spans else None,
        }

    @staticmethod
    async def list_traces(db: AsyncSession, limit: int = 20) -> list[dict]:
        from sqlalchemy import func

        result = await db.execute(
            select(
                AgentTrace.trace_id,
                func.min(AgentTrace.start_time).label("start"),
                func.max(AgentTrace.end_time).label("end"),
                func.count(AgentTrace.id).label("spans"),
                func.sum(AgentTrace.token_count).label("tokens"),
            )
            .group_by(AgentTrace.trace_id)
            .order_by(func.min(AgentTrace.start_time).desc())
            .limit(limit)
        )
        return [
            {
                "trace_id": row[0],
                "start_time": row[1].isoformat() if row[1] else None,
                "end_time": row[2].isoformat() if row[2] else None,
                "spans": row[3],
                "total_tokens": row[4] or 0,
            }
            for row in result
        ]


agent_tracer = AgentTracer()
