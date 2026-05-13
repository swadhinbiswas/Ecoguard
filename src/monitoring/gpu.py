"""GPU monitoring — collect nvidia-smi metrics and expose as Prometheus."""

import asyncio
import subprocess
from typing import Any, Optional

from prometheus_client import Gauge

from src.core.logging import logger

# ── Prometheus Metrics ────────────────────────────────────────

gpu_count = Gauge("ecoguard_gpu_count", "Number of GPUs detected")
gpu_utilization = Gauge(
    "ecoguard_gpu_utilization_percent",
    "GPU utilization percentage",
    ["device", "uuid"],
)
gpu_memory_used = Gauge(
    "ecoguard_gpu_memory_used_mb", "GPU memory used in MB", ["device", "uuid"]
)
gpu_memory_total = Gauge(
    "ecoguard_gpu_memory_total_mb", "GPU total memory in MB", ["device", "uuid"]
)
gpu_temperature = Gauge(
    "ecoguard_gpu_temperature_celsius",
    "GPU temperature in Celsius",
    ["device", "uuid"],
)
gpu_power_draw = Gauge(
    "ecoguard_gpu_power_draw_watts", "GPU power draw in watts", ["device", "uuid"]
)
gpu_fan_speed = Gauge(
    "ecoguard_gpu_fan_speed_percent", "GPU fan speed percent", ["device", "uuid"]
)
gpu_clock = Gauge("ecoguard_gpu_clock_mhz", "GPU SM clock in MHz", ["device", "uuid"])


class GPUMonitor:
    def __init__(self, nvidia_smi_path: str = "nvidia-smi"):
        self.nvidia_smi = nvidia_smi_path
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            result = subprocess.run(
                [self.nvidia_smi, "-L"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self._available = result.returncode == 0
            return self._available
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._available = False
            return False

    def _query(self, query: str) -> list[dict[str, str]]:
        try:
            result = subprocess.run(
                [
                    self.nvidia_smi,
                    "--query-gpu=" + query,
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return []

            fields = query.split(",")
            gpus: list[dict[str, str]] = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                values = [v.strip() for v in line.split(",")]
                gpus.append(dict(zip(fields, values)))
            return gpus
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []

    async def collect(self) -> list[dict[str, Any]]:
        if not self.is_available():
            return []

        return await asyncio.to_thread(self._collect_sync)

    def _collect_sync(self) -> list[dict[str, Any]]:
        query = "index,name,uuid,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,fan.speed,clocks.sm"
        data = self._query(query)
        if not data:
            return []

        gpu_count.set(len(data))
        results: list[dict[str, Any]] = []

        for gpu in data:
            idx = gpu.get("index", "0")
            uuid_val = gpu.get("uuid", "")
            name = gpu.get("name", "")

            util = float(gpu.get("utilization.gpu [%]", 0) or 0)
            mem_used = float(gpu.get("memory.used [MiB]", 0) or 0)
            mem_total = float(gpu.get("memory.total [MiB]", 0) or 0)
            temp = float(gpu.get("temperature.gpu", 0) or 0)
            power = float(gpu.get("power.draw [W]", 0) or 0)
            fan = float(gpu.get("fan.speed [%]", 0) or 0)
            clock = float(gpu.get("clocks.current.sm [MHz]", 0) or 0)

            gpu_utilization.labels(device=idx, uuid=uuid_val).set(util)
            gpu_memory_used.labels(device=idx, uuid=uuid_val).set(mem_used)
            gpu_memory_total.labels(device=idx, uuid=uuid_val).set(mem_total)
            gpu_temperature.labels(device=idx, uuid=uuid_val).set(temp)
            gpu_power_draw.labels(device=idx, uuid=uuid_val).set(power)
            gpu_fan_speed.labels(device=idx, uuid=uuid_val).set(fan)
            gpu_clock.labels(device=idx, uuid=uuid_val).set(clock)

            results.append(
                {
                    "index": idx,
                    "name": name,
                    "uuid": uuid_val,
                    "utilization_pct": util,
                    "memory_used_mb": mem_used,
                    "memory_total_mb": mem_total,
                    "temperature_c": temp,
                    "power_draw_w": power,
                    "fan_speed_pct": fan,
                    "clock_mhz": clock,
                }
            )

        return results

    async def run_collection_loop(self, interval: int = 15) -> None:
        logger.info(f"GPU monitoring started (interval={interval}s)")
        while True:
            try:
                await self.collect()
            except Exception as e:
                logger.error(f"GPU collection failed: {e}")
            await asyncio.sleep(interval)


gpu_monitor = GPUMonitor()
