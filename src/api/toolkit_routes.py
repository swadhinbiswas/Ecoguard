"""Routes for RAG, leaderboard, prompt optimizer, HF Hub, model chain, observability export."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.mlops.rag import rag_pipeline
from src.mlops.toolkit import (
    external_obs,
    hf_hub,
    leaderboard,
    model_chain,
    prompt_optimizer,
)

toolkit_router = APIRouter(prefix="/api/v1", tags=["Toolkit"])


# ── #1 RAG Pipeline ────────────────────────────────────────────


class RAGIngestRequest(BaseModel):
    name: str
    content: str
    source: str = ""


class RAGQueryRequest(BaseModel):
    question: str
    top_k: int = 5


@toolkit_router.post("/rag/ingest")
async def rag_ingest(body: RAGIngestRequest, db: AsyncSession = Depends(get_db)):
    doc = await rag_pipeline.ingest_text(db, body.name, body.content, body.source)
    return {"id": doc.id, "name": doc.name, "chunks": doc.chunk_count}


@toolkit_router.get("/rag/documents")
async def rag_list_documents(db: AsyncSession = Depends(get_db)):
    return {"documents": await rag_pipeline.list_documents(db)}


@toolkit_router.post("/rag/query")
async def rag_query(body: RAGQueryRequest, db: AsyncSession = Depends(get_db)):
    result = await rag_pipeline.query(db, body.question, body.top_k)
    return result


@toolkit_router.delete("/rag/documents/{doc_id}")
async def rag_delete(doc_id: int, db: AsyncSession = Depends(get_db)):
    await rag_pipeline.delete_document(db, doc_id)
    return {"deleted": doc_id}


# ── #2 Model Leaderboard ───────────────────────────────────────


@toolkit_router.get("/leaderboard")
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    return await leaderboard.get_rankings(db)


# ── #3 Prompt Optimizer ────────────────────────────────────────


class PromptOptimizeRequest(BaseModel):
    prompt: str


class PromptCompareRequest(BaseModel):
    prompt_a: str
    prompt_b: str
    test_input: str = ""


@toolkit_router.post("/prompts/optimize")
async def optimize_prompt(body: PromptOptimizeRequest):
    return await prompt_optimizer.optimize(body.prompt)


@toolkit_router.post("/prompts/compare")
async def compare_prompts(body: PromptCompareRequest):
    return await prompt_optimizer.compare_prompts(
        body.prompt_a, body.prompt_b, body.test_input
    )


# ── #4 HuggingFace Hub ─────────────────────────────────────────


@toolkit_router.get("/huggingface/search")
async def search_hf_models(
    query: str = Query(...), limit: int = Query(default=10, le=50)
):
    results = await hf_hub.search_models(query, limit)
    return {"results": results}


@toolkit_router.get("/huggingface/models/{model_id:path}")
async def get_hf_model_info(model_id: str):
    return await hf_hub.get_model_info(model_id)


class HFDownloadRequest(BaseModel):
    model_id: str
    output_dir: str = "./models"
    filename: str | None = None


@toolkit_router.post("/huggingface/download")
async def download_hf_model(body: HFDownloadRequest):
    return await hf_hub.download_model(body.model_id, body.output_dir, body.filename)


# ── #7 Model Chain Builder ─────────────────────────────────────


class ChainStep(BaseModel):
    role: str = "step"
    prompt: str = "{input}"
    max_tokens: int = 256
    temperature: float = 0.7


class ChainRequest(BaseModel):
    input_text: str
    steps: list[ChainStep] = Field(..., min_length=1, max_length=10)


@toolkit_router.post("/chain/run")
async def run_model_chain(body: ChainRequest):
    steps_dict = [s.model_dump() for s in body.steps]
    return await model_chain.run_chain(steps_dict, body.input_text)


# ── #8 External Observability Export ────────────────────────────


class ExportLangSmithRequest(BaseModel):
    trace_id: str
    api_key: str
    endpoint: str | None = None


@toolkit_router.post("/export/langsmith")
async def export_langsmith(body: ExportLangSmithRequest):
    return await external_obs.export_to_langsmith(
        body.trace_id, body.api_key, body.endpoint
    )


class ExportWandbRequest(BaseModel):
    run_name: str
    metrics: dict
    api_key: str


@toolkit_router.post("/export/wandb")
async def export_wandb(body: ExportWandbRequest):
    return await external_obs.export_to_wandb(body.run_name, body.metrics, body.api_key)


@toolkit_router.get("/export/traces")
async def export_traces_json(
    limit: int = Query(default=100, le=1000), db: AsyncSession = Depends(get_db)
):
    traces = await external_obs.export_traces_json(db, limit)
    return {"traces": traces}
