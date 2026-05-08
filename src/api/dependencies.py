from fastapi import Request

from src.monitoring.metrics import record_inference, set_drift_score


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def record_metrics(
    latency_ms: float,
    token_count: int,
    drift_score: float,
    success: bool = True,
) -> None:
    record_inference(latency_ms, token_count, success)
    set_drift_score(drift_score)
