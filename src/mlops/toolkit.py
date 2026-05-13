"""Model leaderboard, prompt auto-optimizer, HuggingFace hub connector,
model chain builder, and external observability exports."""

import asyncio
import json
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.logging import logger
from src.mlops.models import ModelRegistry, ModelStatus
from src.models.inference import InferenceLog

# ── #2 Model Leaderboard ───────────────────────────────────────


class ModelLeaderboard:
    @staticmethod
    async def get_rankings(db: AsyncSession) -> dict[str, Any]:
        models_result = await db.execute(
            select(ModelRegistry).where(
                ModelRegistry.status.in_(
                    [
                        ModelStatus.PRODUCTION,
                        ModelStatus.STAGING,
                        ModelStatus.REGISTERED,
                    ]
                )
            )
        )
        models = models_result.scalars().all()

        rankings: list[dict] = []
        for model in models:
            logs_result = await db.execute(
                select(
                    func.count(InferenceLog.id).label("total"),
                    func.avg(InferenceLog.latency_ms).label("avg_latency"),
                    func.avg(InferenceLog.token_count).label("avg_tokens"),
                    func.avg(InferenceLog.drift_score).label("avg_drift"),
                ).where(InferenceLog.input_text.contains(model.name))
            )
            row = logs_result.one_or_none()
            if not row:
                continue

            total, avg_lat, avg_tok, avg_drift = row
            if total == 0:
                continue

            latency_score = max(0, 100 - (avg_lat or 500) / 10)
            tokens_score = min(100, (avg_tok or 20) * 2)
            drift_penalty = (avg_drift or 0) * 100
            quality_score = max(0, 100 - drift_penalty)

            overall = latency_score * 0.3 + tokens_score * 0.2 + quality_score * 0.5
            rankings.append(
                {
                    "model": model.name,
                    "version": model.version,
                    "status": model.status.value
                    if hasattr(model.status, "value")
                    else str(model.status),
                    "total_requests": total,
                    "avg_latency_ms": round(avg_lat or 0, 2),
                    "avg_tokens": round(avg_tok or 0, 2),
                    "avg_drift": round(avg_drift or 0, 4),
                    "latency_score": round(latency_score, 2),
                    "quality_score": round(quality_score, 2),
                    "overall_score": round(overall, 2),
                }
            )

        rankings.sort(key=lambda x: -x["overall_score"])
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        return {"rankings": rankings, "total_models": len(rankings)}


leaderboard = ModelLeaderboard()


# ── #3 Prompt Auto-Optimizer ───────────────────────────────────


class PromptOptimizer:
    _optimization_prompt = """You are a prompt engineering expert. Analyze the following prompt and suggest improvements.

Original prompt:
{original}

Analyze this prompt for:
1. Clarity — is it clear what is being asked?
2. Specificity — are there enough details?
3. Structure — is the prompt well-structured?
4. Constraints — are constraints explicit?
5. Tone — is the tone appropriate?

Then provide:
- Issues: list specific problems
- Improved: a rewritten, improved version of the prompt
- Explanation: why the improved version is better

Respond in JSON format:
{{"issues": ["...", "..."], "improved": "...", "explanation": "..."}}"""

    @staticmethod
    async def optimize(prompt: str) -> dict[str, Any]:
        backend = get_backend()
        if not backend.is_loaded():
            return {"error": "No model loaded for optimization"}

        optimize_prompt = PromptOptimizer._optimization_prompt.format(original=prompt)
        t0 = time.perf_counter()

        try:
            result = await asyncio.to_thread(
                lambda: backend.generate(
                    prompt=optimize_prompt, max_tokens=512, temperature=0.3
                )
            )
            output = result["choices"][0]["text"]
            latency_ms = (time.perf_counter() - t0) * 1000

            try:
                parsed = json.loads(output)
                return {
                    "original": prompt,
                    "issues": parsed.get("issues", []),
                    "improved": parsed.get("improved", prompt),
                    "explanation": parsed.get("explanation", ""),
                    "optimization_latency_ms": round(latency_ms, 2),
                }
            except json.JSONDecodeError:
                return {
                    "original": prompt,
                    "issues": ["Could not parse optimization result"],
                    "improved": prompt,
                    "explanation": output[:500],
                    "optimization_latency_ms": round(latency_ms, 2),
                }
        except Exception as e:
            return {"error": str(e), "original": prompt}

    @staticmethod
    async def compare_prompts(prompt_a: str, prompt_b: str, test_input: str) -> dict:
        """Test two prompts against the same input and compare outputs."""
        backend = get_backend()

        async def _test(p: str) -> dict:
            t0 = time.perf_counter()
            result = await asyncio.to_thread(
                lambda pr=p: backend.generate(
                    prompt=pr.format(input=test_input)
                    if "{input}" in pr
                    else pr + f"\n\n{test_input}",
                    max_tokens=256,
                    temperature=0.7,
                )
            )
            return {
                "output": result["choices"][0]["text"],
                "tokens": result["usage"]["completion_tokens"],
                "latency_ms": (time.perf_counter() - t0) * 1000,
            }

        result_a, result_b = await asyncio.gather(_test(prompt_a), _test(prompt_b))
        return {
            "prompt_a": {
                "output": result_a["output"],
                "tokens": result_a["tokens"],
                "latency_ms": round(result_a["latency_ms"], 2),
            },
            "prompt_b": {
                "output": result_b["output"],
                "tokens": result_b["tokens"],
                "latency_ms": round(result_b["latency_ms"], 2),
            },
        }


prompt_optimizer = PromptOptimizer()


# ── #4 HuggingFace Hub Connector ───────────────────────────────


class HFHubConnector:
    _base_url = "https://huggingface.co/api"

    @staticmethod
    async def search_models(query: str, limit: int = 10) -> list[dict]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    f"{HFHubConnector._base_url}/models",
                    params={"search": query, "limit": limit, "filter": "gguf"},
                )
                if r.status_code == 200:
                    models = r.json()
                    return [
                        {
                            "id": m.get("id", ""),
                            "author": m.get("author", ""),
                            "downloads": m.get("downloads", 0),
                            "likes": m.get("likes", 0),
                            "tags": m.get("tags", []),
                            "pipeline_tag": m.get("pipeline_tag", ""),
                        }
                        for m in models
                    ]
        except Exception as e:
            logger.warning(f"HF search failed: {e}")
        return []

    @staticmethod
    async def get_model_info(model_id: str) -> dict[str, Any]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{HFHubConnector._base_url}/models/{model_id}")
                if r.status_code == 200:
                    info = r.json()
                    return {
                        "id": info.get("id"),
                        "author": info.get("author"),
                        "sha": info.get("sha"),
                        "last_modified": info.get("lastModified"),
                        "downloads": info.get("downloads"),
                        "likes": info.get("likes"),
                        "siblings": [
                            {"name": s.get("rfilename"), "size": s.get("size")}
                            for s in info.get("siblings", [])
                        ],
                    }
        except Exception as e:
            logger.warning(f"HF model info failed: {e}")
        return {"error": "Failed to fetch model info"}

    @staticmethod
    async def download_model(
        model_id: str, output_dir: str = "./models", filename: str | None = None
    ) -> dict:
        import os
        import subprocess

        os.makedirs(output_dir, exist_ok=True)

        try:
            cmd = ["huggingface-cli", "download", model_id, "--local-dir", output_dir]
            if filename:
                cmd.extend([filename])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {
                "status": "success" if result.returncode == 0 else "failed",
                "model_id": model_id,
                "output_dir": output_dir,
                "stdout": result.stdout[-500:],
                "stderr": result.stderr[-500:] if result.returncode != 0 else "",
            }
        except FileNotFoundError:
            return {
                "status": "cli_not_found",
                "message": "huggingface-cli not installed. Run: pip install huggingface-hub",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


hf_hub = HFHubConnector()


# ── #7 Model Chain Builder ─────────────────────────────────────


class ModelChain:
    @staticmethod
    async def run_chain(steps: list[dict], input_text: str) -> dict[str, Any]:
        """Run a chain of LLM calls. Each step's output becomes the next step's input.
        steps: [{"role": "summarize", "prompt": "Summarize: {input}"}, ...]"""
        backend = get_backend()
        result = input_text
        step_results: list[dict] = []
        total_latency = 0
        total_tokens = 0

        for i, step in enumerate(steps):
            t0 = time.perf_counter()
            try:
                prompt = step.get("prompt", "{input}").replace("{input}", result)
                model_kwargs = {
                    "prompt": prompt,
                    "max_tokens": step.get("max_tokens", 256),
                    "temperature": step.get("temperature", 0.7),
                }

                output = await asyncio.to_thread(
                    lambda: backend.generate(**model_kwargs)
                )
                output_text = output["choices"][0]["text"]
                tokens = output["usage"]["completion_tokens"]
                latency = (time.perf_counter() - t0) * 1000
                total_latency += latency
                total_tokens += tokens

                step_results.append(
                    {
                        "step": i + 1,
                        "role": step.get("role", "step"),
                        "input_preview": result[:200],
                        "output": output_text,
                        "tokens": tokens,
                        "latency_ms": round(latency, 2),
                        "status": "success",
                    }
                )
                result = output_text

            except Exception as e:
                step_results.append(
                    {
                        "step": i + 1,
                        "role": step.get("role", "step"),
                        "status": "failed",
                        "error": str(e),
                    }
                )
                break

        return {
            "input": input_text,
            "output": result,
            "steps": step_results,
            "total_steps_completed": len(
                [s for s in step_results if s["status"] == "success"]
            ),
            "total_latency_ms": round(total_latency, 2),
            "total_tokens": total_tokens,
        }


model_chain = ModelChain()


# ── #8 External Observability Export ────────────────────────────


class ExternalObservability:
    @staticmethod
    async def export_to_langsmith(
        trace_id: str, api_key: str, endpoint: str | None = None
    ) -> dict:
        """Export a trace to LangSmith-compatible endpoint."""
        import httpx

        base = endpoint or "https://api.smith.langchain.com"
        url = f"{base}/runs"

        payload = {
            "id": trace_id,
            "name": f"eco-guard-{trace_id}",
            "run_type": "chain",
            "inputs": {},
            "outputs": {},
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    url,
                    json=payload,
                    headers={"x-api-key": api_key, "Content-Type": "application/json"},
                )
                return {
                    "status": "success" if r.status_code == 200 else "failed",
                    "http_status": r.status_code,
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def export_to_wandb(run_name: str, metrics: dict, api_key: str) -> dict:
        """Export metrics to Weights & Biases."""
        try:
            import wandb  # type: ignore

            wandb.login(key=api_key)
            run = wandb.init(project="eco-guard", name=run_name, reinit=True)
            run.log(metrics)
            run.finish()
            return {"status": "success", "run": run_name}
        except ImportError:
            return {"status": "no_wandb", "message": "pip install wandb"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def export_traces_json(db: AsyncSession, limit: int = 100) -> list[dict]:
        from src.core.agent_tracing import AgentTrace

        result = await db.execute(
            select(AgentTrace).order_by(AgentTrace.start_time.desc()).limit(limit)
        )
        spans = result.scalars().all()

        return [
            {
                "trace_id": s.trace_id,
                "span_id": s.span_id,
                "parent_span_id": s.parent_span_id,
                "span_type": s.span_type,
                "name": s.name,
                "status": s.status,
                "duration_ms": s.duration_ms,
                "token_count": s.token_count,
                "model": s.model,
                "input": s.input_data,
                "output": s.output_data,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
            }
            for s in spans
        ]


external_obs = ExternalObservability()
