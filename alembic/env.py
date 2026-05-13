import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from src.db.database import Base
from src.models.inference import InferenceLog  # noqa: F401

# Import all models so autogenerate detects all tables
from src.mlops.models import (  # noqa: F401
    Dataset,
    Deployment,
    ModelRegistry,
    RetrainingTrigger,
    TrainingExperiment,
    TrainingJob,
)
from src.core.workspaces import (  # noqa: F401
    Workspace,
    WorkspaceMember,
    WorkspaceAPIKey,
    TokenQuota,
)
from src.mlops.dashboard_data import PromptTemplate, AlertRule  # noqa: F401
from src.mlops.advanced import PromptVersion, ABTestResult, UserFeedback  # noqa: F401
from src.core.agent_tracing import AgentTrace  # noqa: F401
from src.mlops.rag import Document, DocumentChunk  # noqa: F401
from src.core.enterprise import Budget, ScalingRule  # noqa: F401
from src.mlops.quality import RegressionCheck, AnomalyLog  # noqa: F401
from src.mlops.gov import ScheduledJob, ScheduledJobRun, AuditEntry  # noqa: F401
from src.core.config import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
