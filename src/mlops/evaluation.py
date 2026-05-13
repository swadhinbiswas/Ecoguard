import asyncio
import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.models.inference import InferenceLog


class ModelEvaluator:
    def __init__(self, test_cases: list[dict] | None = None):
        self.test_cases = test_cases or [
            {"prompt": "The capital of France is", "expected_tokens": 3},
            {"prompt": "1 + 1 =", "expected_tokens": 1},
            {"prompt": "The color of the sky is", "expected_tokens": 3},
            {"prompt": "Python is a", "expected_tokens": 5},
        ]

    async def evaluate(
        self,
        model_path: str | None = None,
        verbose: bool = False,
    ) -> dict:
        backend = get_backend()
        is_llama_cpp = backend.__class__.__name__ == "LlamaCppBackend"

        if model_path and backend.info.get("path") != model_path:
            try:
                backend.load(model_path)
            except Exception as e:
                return {"error": str(e), "status": "model_load_failed"}

        if not backend.is_loaded():
            return {"error": "No model loaded", "status": "no_model"}

        results = []
        total_latency = 0.0
        total_tokens = 0
        start_time = time.perf_counter()

        for tc in self.test_cases:
            t_start = time.perf_counter()

            try:
                if is_llama_cpp:
                    output = await asyncio.to_thread(
                        backend.generate,
                        prompt=tc["prompt"],
                        max_tokens=tc.get("max_tokens", 50),
                        temperature=0.0,
                    )
                else:
                    output = backend.generate(
                        prompt=tc["prompt"],
                        max_tokens=tc.get("max_tokens", 50),
                        temperature=0.0,
                    )

                t_latency = (time.perf_counter() - t_start) * 1000
                text = output["choices"][0]["text"]
                tokens = output["usage"]["completion_tokens"]

                total_latency += t_latency
                total_tokens += tokens

                results.append(
                    {
                        "prompt": tc["prompt"],
                        "output": text.strip(),
                        "tokens": tokens,
                        "latency_ms": round(t_latency, 2),
                        "passed": tokens > 0,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "prompt": tc["prompt"],
                        "error": str(e),
                        "passed": False,
                    }
                )

        elapsed = (time.perf_counter() - start_time) * 1000
        passed = sum(1 for r in results if r.get("passed"))
        failed = len(results) - passed

        return {
            "status": "completed",
            "model": backend.info.get("path"),
            "test_cases": len(self.test_cases),
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / len(self.test_cases) * 100, 2)
            if self.test_cases
            else 0,
            "total_latency_ms": round(total_latency, 2),
            "avg_latency_ms": round(total_latency / len(self.test_cases), 2)
            if self.test_cases
            else 0,
            "total_tokens": total_tokens,
            "tokens_per_second": round(total_tokens / (total_latency / 1000), 2)
            if total_latency > 0
            else 0,
            "elapsed_ms": round(elapsed, 2),
            "results": results,
        }

    @staticmethod
    async def evaluate_from_logs(
        db: AsyncSession,
        sample_size: int = 20,
    ) -> dict:
        result = await db.execute(
            select(InferenceLog.input_text, InferenceLog.prediction_output)
            .where(InferenceLog.token_count > 0)
            .order_by(func.random())
            .limit(sample_size)
        )
        rows = result.all()

        test_cases = [
            {"prompt": r.input_text, "expected_tokens": 5} for r in rows if r.input_text
        ]

        if not test_cases:
            return {
                "status": "no_data",
                "message": "No inference logs available for evaluation",
            }

        evaluator = ModelEvaluator(test_cases=test_cases)
        return await evaluator.evaluate()
