import asyncio
import json
import time
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.core.config import settings
from src.core.backend import get_backend
from src.core.logging import logger
from src.services.drift_detector import drift_detector
from src.core.concurrency import inference_limiter

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
                    "recent": [round(l, 2) for l in latencies],
                },
                "drift": {
                    "samples": len(drift_detector._latency_history),
                },
            }
            await broadcast_metrics(payload)
        except Exception as e:
            logger.error(f"Metrics broadcast error: {e}")
        await asyncio.sleep(2)


@ws_router.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket):
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
