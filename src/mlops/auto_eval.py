"""Automated evaluation pipeline — gate deployments on quality checks."""

import asyncio
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.backend import get_backend
from src.core.events import EventType, emit
from src.core.logging import logger


class AutoEvalPipeline:
    def __init__(self, pass_threshold: float = 0.7):
        self.pass_threshold = pass_threshold
        self._eval_suites: dict[str, list[dict]] = {}

    def register_suite(self, name: str, test_cases: list[dict]) -> None:
        self._eval_suites[name] = test_cases
        logger.info(f"Eval suite registered: {name} ({len(test_cases)} cases)")

    async def run_suite(
        self,
        suite_name: str,
        model_path: str | None = None,
    ) -> dict[str, Any]:
        if suite_name not in self._eval_suites:
            return {"error": f"Suite '{suite_name}' not found"}

        test_cases = self._eval_suites[suite_name]
        backend = get_backend()

        results: list[dict] = []
        passed = 0
        total_latency = 0.0
        total_tokens = 0

        for case in test_cases:
            t0 = time.perf_counter()
            try:
                output = await asyncio.to_thread(
                    lambda: backend.generate(
                        prompt=case["prompt"],
                        max_tokens=case.get("max_tokens", 50),
                        temperature=0.0,
                    )
                )
                latency = (time.perf_counter() - t0) * 1000
                output_text = output["choices"][0]["text"]
                tokens = output["usage"]["completion_tokens"]
                total_latency += latency
                total_tokens += tokens

                expected = case.get("expected", "")
                check_type = case.get("check", "contains")
                ok = False

                if check_type == "contains":
                    ok = expected.lower() in output_text.lower()
                elif check_type == "regex":
                    import re

                    ok = bool(re.search(expected, output_text))
                elif check_type == "exact":
                    ok = output_text.strip() == expected.strip()

                if ok:
                    passed += 1

                results.append(
                    {
                        "prompt": case["prompt"][:100],
                        "output": output_text[:200],
                        "expected": expected,
                        "passed": ok,
                        "latency_ms": round(latency, 2),
                        "tokens": tokens,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "prompt": case["prompt"][:100],
                        "error": str(e),
                        "passed": False,
                    }
                )

        total = len(test_cases)
        score = passed / total if total > 0 else 0
        passed_check = score >= self.pass_threshold

        summary = {
            "suite": suite_name,
            "passed": passed,
            "total": total,
            "score": round(score, 4),
            "passed_threshold": passed_check,
            "threshold": self.pass_threshold,
            "avg_latency_ms": round(total_latency / total, 2) if total > 0 else 0,
            "total_tokens": total_tokens,
            "results": results,
        }

        if not passed_check:
            logger.warning(
                f"Eval suite '{suite_name}' failed: {passed}/{total} "
                f"(score={score:.2f}, threshold={self.pass_threshold})"
            )

        await emit(EventType.JOB_COMPLETED, {"type": "eval", "summary": summary})
        return summary

    async def gate_deployment(
        self,
        suite_name: str,
        db: AsyncSession,
    ) -> tuple[bool, dict]:
        result = await self.run_suite(suite_name)
        if result.get("error"):
            return False, result

        passed = result["passed_threshold"]
        if not passed:
            logger.warning(
                f"Deployment gated by eval suite '{suite_name}': "
                f"score {result['score']} < {self.pass_threshold}"
            )

        return passed, result


auto_eval = AutoEvalPipeline(pass_threshold=0.7)
