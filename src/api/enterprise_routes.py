"""New API routes: workspaces, webhooks, plugins, auto-eval, SSO, token counting, IP allowlist."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import create_token, verify_request
from src.core.config import settings
from src.core.events import (
    deregister_webhook,
    emit,
    register_webhook,
    setup_default_webhooks,
)
from src.core.plugins import list_plugins, load_plugin_from_path
from src.core.scoped_keys import get_ip_allowlist, token_counter
from src.core.sso import get_sso_providers
from src.core.workspaces import WorkspaceRole, WorkspaceService
from src.db.session import get_db
from src.mlops.auto_eval import auto_eval
from src.services.semantic_cache import semantic_cache

enterprise_router = APIRouter(prefix="/api/v1", tags=["Enterprise"])


# ── Workspaces ─────────────────────────────────────────────────


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    slug: str = Field(..., min_length=1, max_length=128)
    description: str = ""


@enterprise_router.post("/workspaces")
async def create_workspace(
    body: CreateWorkspaceRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = verify_request(request)
    username = user["sub"] if user else "admin"
    ws = await WorkspaceService.create_workspace(
        db, body.name, body.slug, username, body.description
    )
    return {"id": ws.id, "name": ws.name, "slug": ws.slug}


@enterprise_router.get("/workspaces")
async def list_workspaces(request: Request, db: AsyncSession = Depends(get_db)):
    user = verify_request(request)
    username = user["sub"] if user else "admin"
    workspaces = await WorkspaceService.list_workspaces(db, username)
    return [
        {"id": w.id, "name": w.name, "slug": w.slug, "description": w.description}
        for w in workspaces
    ]


@enterprise_router.post("/workspaces/{slug}/members")
async def add_member(
    slug: str,
    username: str = Query(...),
    role: str = Query(default="member"),
    db: AsyncSession = Depends(get_db),
):
    role_enum = WorkspaceRole(role)
    await WorkspaceService.add_member(db, slug, username, role_enum)
    return {"workspace_slug": slug, "username": username, "role": role_enum.value}


@enterprise_router.post("/workspaces/{slug}/quota")
async def set_workspace_quota(
    slug: str,
    max_tokens: int = Query(..., ge=1),
    period: str = Query(default="monthly"),
    db: AsyncSession = Depends(get_db),
):
    ws = await WorkspaceService.get_workspace(db, slug)
    if not ws:
        raise HTTPException(404, "Workspace not found")
    quota = await WorkspaceService.set_quota(db, ws.id, max_tokens, period)
    return {
        "workspace_id": ws.id,
        "max_tokens": quota.max_tokens,
        "period": quota.period,
    }


# ── Webhooks ───────────────────────────────────────────────────


class WebhookRegisterRequest(BaseModel):
    url: str


@enterprise_router.post("/webhooks")
async def register_webhook_endpoint(body: WebhookRegisterRequest):
    register_webhook(body.url)
    setup_default_webhooks()
    return {"registered": body.url, "total": 1}


@enterprise_router.get("/webhooks")
async def list_webhooks():
    from src.core.events import _webhook_urls

    return {"webhooks": _webhook_urls}


@enterprise_router.delete("/webhooks")
async def delete_webhook(url: str = Query(...)):
    deregister_webhook(url)
    return {"removed": url}


@enterprise_router.post("/webhooks/test")
async def test_webhook(url: str = Query(...)):
    await emit("test.event", {"message": "This is a test webhook event"})
    return {"delivered_to": url}


# ── Plugins ────────────────────────────────────────────────────


class PluginLoadRequest(BaseModel):
    category: str
    module: str
    class_name: str


@enterprise_router.post("/plugins/load")
async def load_plugin(body: PluginLoadRequest):
    load_plugin_from_path(body.category, body.module, body.class_name)
    return {
        "category": body.category,
        "module": body.module,
        "class_name": body.class_name,
    }


@enterprise_router.get("/plugins")
async def list_all_plugins():
    return {
        "backends": list(list_plugins("backends").keys()),
        "guardrails": list(list_plugins("guardrails").keys()),
        "evaluators": list(list_plugins("evaluators").keys()),
        "middleware": list(list_plugins("middleware").keys()),
    }


# ── Auto Eval ──────────────────────────────────────────────────


class EvalSuiteRequest(BaseModel):
    name: str
    test_cases: list[dict]


@enterprise_router.post("/eval/suites")
async def register_eval_suite(body: EvalSuiteRequest):
    auto_eval.register_suite(body.name, body.test_cases)
    return {"name": body.name, "test_cases": len(body.test_cases)}


@enterprise_router.post("/eval/run/{suite_name}")
async def run_eval_suite(suite_name: str):
    result = await auto_eval.run_suite(suite_name)
    return result


@enterprise_router.post("/eval/gate-deploy/{suite_name}")
async def gate_deploy(suite_name: str, db: AsyncSession = Depends(get_db)):
    passed, result = await auto_eval.gate_deployment(suite_name, db)
    return {"passed": passed, **result}


# ── SSO ────────────────────────────────────────────────────────


@enterprise_router.get("/auth/sso/providers")
async def list_sso_providers():
    providers = get_sso_providers()
    return {"providers": list(providers.keys())}


@enterprise_router.get("/auth/sso/{provider}/login")
async def sso_login(provider: str, redirect_uri: str = Query(...)):
    providers = get_sso_providers()
    if provider not in providers:
        raise HTTPException(400, f"Unknown provider: {provider}")

    state = secrets.token_urlsafe(32)
    auth_url = providers[provider].get_authorization_url(redirect_uri, state)
    return {"url": auth_url, "state": state}


@enterprise_router.get("/auth/sso/{provider}/callback")
async def sso_callback(
    provider: str,
    code: str = Query(...),
    redirect_uri: str = Query(...),
):
    providers = get_sso_providers()
    if provider not in providers:
        raise HTTPException(400, f"Unknown provider: {provider}")

    user_info = await providers[provider].exchange_code(code, redirect_uri)
    if not user_info:
        raise HTTPException(401, "SSO authentication failed")

    token = create_token(sub=user_info.get("email", "sso-user"), role="member")
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_info,
    }


# ── Token Counting ─────────────────────────────────────────────


@enterprise_router.get("/utils/tokenize")
async def count_tokens(text: str = Query(..., min_length=1)):
    count = token_counter.count(text)
    return {"text": text[:200], "estimated_tokens": count}


@enterprise_router.post("/utils/tokenize/batch")
async def count_tokens_batch(texts: list[str]):
    counts = token_counter.count_batch(texts)
    return {
        "results": [
            {"text": t[:100], "estimated_tokens": c} for t, c in zip(texts, counts)
        ],
        "total_tokens": sum(counts),
    }


# ── IP Allowlist ───────────────────────────────────────────────


@enterprise_router.get("/security/ip-allowlist")
async def get_ip_allowlist_endpoint():
    get_ip_allowlist()
    return {"enabled": bool(settings.ip_allowlist), "cidrs": settings.ip_allowlist}


@enterprise_router.post("/security/ip-check")
async def check_ip(request: Request, ip: str = Query(...)):
    allowlist = get_ip_allowlist()
    allowed = allowlist.is_allowed(ip)
    return {"ip": ip, "allowed": allowed}


# ── Semantic Cache ─────────────────────────────────────────────


@enterprise_router.get("/cache/semantic/status")
async def semantic_cache_status():
    return {
        "enabled": settings.cache_enabled,
        "size": semantic_cache.size,
        "threshold": semantic_cache.threshold,
    }


@enterprise_router.post("/cache/semantic/clear")
async def clear_semantic_cache():
    await semantic_cache.clear()
    return {"cleared": True}


# ── API Key Management ─────────────────────────────────────────


class GenerateKeyRequest(BaseModel):
    name: str = "default"


@enterprise_router.post("/enterprise/keys/generate")
async def generate_api_key(body: GenerateKeyRequest):
    from src.core.auth import get_api_key_store

    store = get_api_key_store()
    key = store.generate_key()
    return {
        "key": key,
        "name": body.name,
        "scopes": ["inference"],
        "preview": key[:8] + "..." + key[-4:],
    }


@enterprise_router.delete("/enterprise/keys/{key_id}")
async def revoke_api_key(key_id: str):
    from src.core.auth import get_api_key_store

    store = get_api_key_store()
    store.revoke_key(key_id)
    return {"revoked": key_id}


@enterprise_router.get("/enterprise/keys")
async def list_api_keys():
    from src.core.auth import get_api_key_store

    store = get_api_key_store()
    return {
        "keys": [
            {
                "id": f"key-{i}",
                "name": "api-key",
                "preview": f"eg-{i:04d}...",
                "scopes": ["inference"],
                "last_used": None,
                "expires_at": None,
            }
            for i in range(store.key_count)
        ]
    }
