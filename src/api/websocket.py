import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.core.backend import get_backend
from src.core.concurrency import inference_limiter
from src.core.logging import logger
from src.services.drift_detector import drift_detector

ws_router = APIRouter()

_connected_clients: set[WebSocket] = set()


async def broadcast_metrics(data: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    payload = json.dumps(data)
    for ws in _connected_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connected_clients.discard(ws)


async def metrics_broadcast_loop() -> None:
    while True:
        try:
            latencies = (
                drift_detector._latency_history[-10:]
                if drift_detector._latency_history
                else [0]
            )

            payload = {
                "timestamp": int(time.time()),
                "model_loaded": get_backend().is_loaded(),
                "concurrency": {
                    "max": inference_limiter.max_concurrent,
                    "in_use": inference_limiter.in_use,
                },
                "latency": {
                    "recent": [round(lat, 2) for lat in latencies],
                    "avg": round(sum(latencies) / max(len(latencies), 1), 2),
                },
                "drift": {
                    "samples": len(drift_detector._latency_history),
                    "tokens": len(drift_detector._token_history)
                    if hasattr(drift_detector, "_token_history")
                    else 0,
                },
                "system": {
                    "cache_size": 0,
                    "rate_limit_enabled": True,
                },
                "queue": {
                    "depth_high": 0,
                    "depth_total": 0,
                },
                "gpu": {
                    "available": False,
                    "utilization": 0,
                    "memory_used_mb": 0,
                    "temperature_c": 0,
                },
            }

            # Enrich with queue depth if available
            try:
                from src.core.enterprise import priority_queue

                payload["queue"] = priority_queue.depth
            except Exception:
                pass

            # Enrich with GPU metrics if available
            try:
                from src.monitoring.gpu import gpu_monitor

                gpus = await gpu_monitor.collect()
                if gpus:
                    g = gpus[0]
                    payload["gpu"] = {
                        "available": True,
                        "utilization": g["utilization_pct"],
                        "memory_used_mb": g["memory_used_mb"],
                        "memory_total_mb": g["memory_total_mb"],
                        "temperature_c": g["temperature_c"],
                    }
            except Exception:
                pass
            await broadcast_metrics(payload)
        except Exception as e:
            logger.error(f"Metrics broadcast error: {e}")
        await asyncio.sleep(2)


@ws_router.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket):
    from urllib.parse import parse_qs

    from src.core.auth import decode_token

    cookie_token = websocket.cookies.get("eco_guard_token")
    query_token = None
    if websocket.url.query:
        query_token = parse_qs(websocket.url.query.decode()).get("token", [None])[0]
    token = cookie_token or query_token
    if token:
        user = decode_token(token)
    else:
        api_key = websocket.headers.get("x-api-key") or websocket.headers.get(
            "X-API-Key"
        )
        if api_key:
            from src.core.auth import get_api_key_store

            store = get_api_key_store()
            user = (
                {"sub": "api-key", "role": "admin"} if store.validate(api_key) else None
            )
        else:
            user = None

    if user is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await websocket.accept()
    _connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"pong":true}')
    except WebSocketDisconnect:
        pass
    finally:
        _connected_clients.discard(websocket)
