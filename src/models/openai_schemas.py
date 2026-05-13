"""OpenAI-compatible API schemas for chat completions, embeddings, and models."""

from typing import Any, Optional

from pydantic import BaseModel, Field

# ── Chat Completion ──────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str = Field(..., description="system, user, assistant, or tool")
    content: str | list[dict] = Field(..., description="Message content")
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[dict]] = None


class ToolFunction(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: dict = Field(default_factory=dict)


class Tool(BaseModel):
    type: str = "function"
    function: ToolFunction


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="default", description="Model ID")
    messages: list[ChatMessage] = Field(..., min_length=1)
    max_tokens: Optional[int] = Field(None, ge=1, le=32768)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(None, ge=1, le=100)
    repeat_penalty: Optional[float] = Field(None, ge=1.0, le=2.0)
    stream: bool = False
    stop: Optional[list[str]] = None
    presence_penalty: float = Field(0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(0.0, ge=-2.0, le=2.0)
    user: Optional[str] = None
    tools: Optional[list[Tool]] = None
    tool_choice: Optional[str | dict] = None
    response_format: Optional[dict] = None
    seed: Optional[int] = None
    n: int = Field(1, ge=1, le=128)


class ChatMessageResponse(BaseModel):
    role: str = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatMessageResponse
    finish_reason: str = "stop"
    logprobs: Optional[Any] = None


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: ChatUsage


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[dict]


# ── Embeddings ────────────────────────────────────────────────


class EmbeddingRequest(BaseModel):
    model: str = Field(default="text-embedding-3-small", description="Model ID")
    input: str | list[str] = Field(..., description="Text to embed")
    user: Optional[str] = None
    encoding_format: str = "float"


class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: list[float]


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingData]
    model: str
    usage: dict


# ── Models ────────────────────────────────────────────────────


class OpenAIModel(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "eco-guard"


class OpenAIModelList(BaseModel):
    object: str = "list"
    data: list[OpenAIModel]


# ── Batch Inference ───────────────────────────────────────────


class BatchRequest(BaseModel):
    prompts: list[str] = Field(..., min_length=1, max_length=100)
    max_tokens: int = Field(128, ge=1, le=2048)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)


class BatchResult(BaseModel):
    index: int
    output: str
    token_count: int
    latency_ms: float
    error: Optional[str] = None


class BatchResponse(BaseModel):
    results: list[BatchResult]
    total_latency_ms: float
    total_tokens: int


# ── Fallback Chain ────────────────────────────────────────────


class FallbackStep(BaseModel):
    model: str
    backend_url: Optional[str] = None
    timeout_seconds: int = 30


class FallbackChainRequest(BaseModel):
    prompt: str
    steps: list[FallbackStep] = Field(..., min_length=1, max_length=5)
    max_tokens: int = Field(128, ge=1, le=2048)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
