"""SSO/OIDC integration — Google, GitHub OAuth login."""

from typing import Optional

import httpx
import jwt  # noqa: F401 — used for ID token validation

from src.core.config import settings
from src.core.logging import logger


class SSOProvider:
    def __init__(self, name: str, client_id: str, client_secret: str, **kwargs):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.config = kwargs

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        raise NotImplementedError

    async def exchange_code(self, code: str, redirect_uri: str) -> Optional[dict]:
        raise NotImplementedError


class GoogleSSO(SSOProvider):
    def __init__(self):
        super().__init__(
            name="google",
            client_id=getattr(settings, "google_client_id", ""),
            client_secret=getattr(settings, "google_client_secret", ""),
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        )

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        from urllib.parse import urlencode

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
        }
        return f"{self.config['authorize_url']}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Optional[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self.config["token_url"],
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if r.status_code != 200:
                logger.error(f"Google token exchange failed: {r.text}")
                return None

            tokens = r.json()
            access_token = tokens.get("access_token")

            if access_token:
                r2 = await client.get(
                    self.config["userinfo_url"],
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if r2.status_code == 200:
                    user_info = r2.json()
                    return {
                        "provider": "google",
                        "email": user_info.get("email"),
                        "name": user_info.get("name"),
                        "sub": user_info.get("sub"),
                        "picture": user_info.get("picture"),
                    }

        return None


class GitHubSSO(SSOProvider):
    def __init__(self):
        super().__init__(
            name="github",
            client_id=getattr(settings, "github_client_id", ""),
            client_secret=getattr(settings, "github_client_secret", ""),
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            userinfo_url="https://api.github.com/user",
            emails_url="https://api.github.com/user/emails",
        )

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        from urllib.parse import urlencode

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "user:email",
            "state": state,
        }
        return f"{self.config['authorize_url']}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Optional[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self.config["token_url"],
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            if r.status_code != 200:
                logger.error(f"GitHub token exchange failed: {r.text}")
                return None

            tokens = r.json()
            access_token = tokens.get("access_token")

            if access_token:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
                r2 = await client.get(self.config["userinfo_url"], headers=headers)
                r3 = await client.get(self.config["emails_url"], headers=headers)

                if r2.status_code == 200:
                    user_info = r2.json()
                    email = user_info.get("email")
                    if not email and r3.status_code == 200:
                        emails = r3.json()
                        primary = [e for e in emails if e.get("primary")]
                        if primary:
                            email = primary[0]["email"]

                    return {
                        "provider": "github",
                        "email": email,
                        "name": user_info.get("name") or user_info.get("login"),
                        "sub": str(user_info.get("id")),
                        "picture": user_info.get("avatar_url"),
                    }

        return None


_sso_providers: dict[str, SSOProvider] = {}


def get_sso_providers() -> dict[str, SSOProvider]:
    global _sso_providers
    if not _sso_providers:
        google_id = getattr(settings, "google_client_id", "")
        github_id = getattr(settings, "github_client_id", "")

        if google_id and getattr(settings, "google_client_secret", ""):
            _sso_providers["google"] = GoogleSSO()
        if github_id and getattr(settings, "github_client_secret", ""):
            _sso_providers["github"] = GitHubSSO()

    return _sso_providers
