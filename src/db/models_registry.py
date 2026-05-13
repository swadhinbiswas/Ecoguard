"""Central model registry — imports all SQLAlchemy models so they register with Base."""

# Core inference models
# Agent tracing
from src.core.agent_tracing import AgentTrace  # noqa: F401

# Enterprise features
from src.core.enterprise import Budget, ScalingRule  # noqa: F401

# Workspaces & multi-tenancy
from src.core.workspaces import (  # noqa: F401
    TokenQuota,
    Workspace,
    WorkspaceAPIKey,
    WorkspaceMember,
)

# Advanced features
from src.mlops.advanced import (  # noqa: F401
    ABTestResult,
    PromptVersion,
    UserFeedback,
)

# Prompt management
from src.mlops.dashboard_data import (  # noqa: F401
    AlertRule,
    PromptTemplate,
)

# Governance
from src.mlops.gov import (  # noqa: F401
    AuditEntry,
    ScheduledJob,
    ScheduledJobRun,
)

# MLOps models (already imported via alembic env.py, but explicit here for create_all)
from src.mlops.models import (  # noqa: F401
    Dataset,
    Deployment,
    ExperimentStatus,
    JobStatus,
    ModelRegistry,
    ModelStatus,
    RetrainingTrigger,
    TrainingExperiment,
    TrainingJob,
)

# Quality & safety
from src.mlops.quality import AnomalyLog, RegressionCheck  # noqa: F401

# RAG pipeline
from src.mlops.rag import Document, DocumentChunk  # noqa: F401
from src.models.inference import InferenceLog  # noqa: F401
