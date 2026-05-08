from pydantic import BaseModel, Field
from typing import Optional


class PredictionRequest(BaseModel):
    prompt: str = Field(..., description="The input text for the LLM")
    max_tokens: int = Field(
        128, ge=1, le=2048, description="Maximum tokens to generate"
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Nucleus sampling probability"
    )
    top_k: Optional[int] = Field(None, ge=1, le=100, description="Top-k sampling")
    repeat_penalty: Optional[float] = Field(
        None, ge=1.0, le=2.0, description="Repetition penalty"
    )


class PredictionResponse(BaseModel):
    request_id: str
    output: str
    latency_ms: float
    token_count: int
    timestamp: str
    drift_score: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    checks: dict[str, str]


class ErrorResponse(BaseModel):
    detail: str


class ModelInfo(BaseModel):
    loaded: bool
    path: Optional[str] = None


class MetricsSummaryResponse(BaseModel):
    model_loaded: bool
    cache_enabled: bool
    cache_size: int
    rate_limit_enabled: bool
    drift_samples: int
