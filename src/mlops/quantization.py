import os
import hashlib
import subprocess
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from src.mlops.models import ModelRegistry, ModelStatus
from src.core.config import settings
from src.core.logging import logger


class QuantizationPipeline:
    QUANT_METHODS = {
        "q4_0": "4-bit, 32-group size (smallest)",
        "q4_k_m": "4-bit, K-quant medium (recommended)",
        "q5_k_m": "5-bit, K-quant medium (higher quality)",
        "q8_0": "8-bit, 32-group size (best quality)",
    }

    @staticmethod
    async def quantize(
        db: AsyncSession,
        source_model_id: int,
        method: str = "q4_k_m",
        output_name: str | None = None,
    ) -> dict:
        method = method.lower()
        if method not in QuantizationPipeline.QUANT_METHODS:
            return {
                "status": "failed",
                "error": f"Unknown quantization method: {method}. Available: {list(QuantizationPipeline.QUANT_METHODS.keys())}",
            }

        from sqlalchemy import select

        result = await db.execute(
            select(ModelRegistry).where(ModelRegistry.id == source_model_id)
        )
        source = result.scalar_one_or_none()
        if not source:
            return {"status": "failed", "error": f"Model {source_model_id} not found"}

        source_path = source.artifact_path
        if not os.path.exists(source_path):
            return {
                "status": "failed",
                "error": f"Source model file not found: {source_path}",
            }

        model_dir = os.path.dirname(source_path) or "models"
        base_name = os.path.splitext(os.path.basename(source_path))[0]
        output_file = os.path.join(model_dir, f"{base_name}-{method}.gguf")

        logger.info(f"Quantizing {source_path} -> {output_file} ({method})")

        try:
            process = await asyncio.create_subprocess_exec(
                "python",
                "-m",
                "llama_cpp.quantize",
                source_path,
                output_file,
                method,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error = stderr.decode() if stderr else "Unknown error"
                return {"status": "failed", "error": error[:500]}

            checksum = hashlib.sha256()
            with open(output_file, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    checksum.update(chunk)

            source_size = os.path.getsize(source_path)
            output_size = os.path.getsize(output_file)
            compression = (
                round((1 - output_size / source_size) * 100, 2)
                if source_size > 0
                else 0
            )

            output_version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

            quantized = ModelRegistry(
                name=output_name or f"{source.name}-{method}",
                version=output_version,
                status=ModelStatus.REGISTERED,
                artifact_path=output_file,
                artifact_checksum=checksum.hexdigest(),
                base_model=source.name,
                framework="llama-cpp",
                parameters={
                    "quantization": method,
                    "source_model_id": source_model_id,
                    "source_size_bytes": source_size,
                    "output_size_bytes": output_size,
                    "compression_ratio": compression,
                },
                description=f"Quantized from {source.name} v{source.version} using {method}",
            )
            db.add(quantized)
            await db.flush()

            return {
                "status": "completed",
                "model_id": quantized.id,
                "name": quantized.name,
                "version": quantized.version,
                "artifact_path": output_file,
                "method": method,
                "source_size_mb": round(source_size / 1024 / 1024, 2),
                "output_size_mb": round(output_size / 1024 / 1024, 2),
                "compression_pct": compression,
            }

        except FileNotFoundError:
            return {
                "status": "failed",
                "error": "llama_cpp.quantize not found. Install llama-cpp-python to enable quantization.",
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)[:500]}
