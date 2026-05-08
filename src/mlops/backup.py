import os
import asyncio
import subprocess
from datetime import datetime, timezone
from src.core.config import settings
from src.core.logging import logger


class BackupService:
    @staticmethod
    async def create_backup(backup_dir: str = "backups") -> dict:
        os.makedirs(backup_dir, exist_ok=True)
        url = settings.database_url

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        filename = f"ecoguard-backup-{timestamp}.sql"

        try:
            db_url = url.replace("+asyncpg", "")
            db_url = db_url.replace("postgresql://", "")

            user, rest = db_url.split(":", 1)
            password, rest = rest.split("@", 1)
            host_port, dbname = rest.split("/", 1)
            host = host_port.split(":")[0]
            port = host_port.split(":")[1] if ":" in host_port else "5432"

            filepath = os.path.join(backup_dir, filename)
            env = os.environ.copy()
            env["PGPASSWORD"] = password

            process = await asyncio.create_subprocess_exec(
                "pg_dump",
                "-h",
                host,
                "-p",
                port,
                "-U",
                user,
                "-d",
                dbname,
                "-f",
                filepath,
                "--no-owner",
                "--no-acl",
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return {
                    "status": "failed",
                    "error": (stderr.decode() if stderr else "Unknown error")[:500],
                }

            size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
            logger.info(f"Backup created: {filepath} ({size / 1024 / 1024:.1f}MB)")

            return {
                "status": "completed",
                "filepath": filepath,
                "filename": filename,
                "size_mb": round(size / 1024 / 1024, 2),
                "timestamp": timestamp,
            }

        except FileNotFoundError:
            return {
                "status": "failed",
                "error": "pg_dump not found. Install PostgreSQL client tools.",
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)[:500]}

    @staticmethod
    async def list_backups(backup_dir: str = "backups") -> list[dict]:
        if not os.path.exists(backup_dir):
            return []

        backups = []
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.startswith("ecoguard-backup-") and f.endswith(".sql"):
                path = os.path.join(backup_dir, f)
                backups.append(
                    {
                        "filename": f,
                        "size_mb": round(os.path.getsize(path) / 1024 / 1024, 2),
                        "created": datetime.fromtimestamp(
                            os.path.getmtime(path)
                        ).isoformat(),
                    }
                )
        return backups
