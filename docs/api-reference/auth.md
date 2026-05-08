# Authentication API

Eco-Guard supports three authentication methods: Bearer JWT tokens, cookie-based sessions, and API keys. The auth API provides login, token management, and status verification.

## POST /api/v1/auth/login

Authenticate with username and password to receive a JWT token.

> This endpoint is public (no authentication required).

### Request

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin" \
  -d "password=admin"
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `username` | Yes | Admin username (configured via `ADMIN_USERNAME`) |
| `password` | Yes | Admin password (configured via `ADMIN_PASSWORD`) |

### Response (200 OK)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Error (401 Unauthorized)

```json
{
  "detail": "Invalid credentials"
}
```

## GET /api/v1/auth/status

Check the current authentication status. Supports Bearer tokens, cookies, and API keys.

> This endpoint is public (no authentication required), but returns different results based on provided credentials.

### Request

```bash
curl http://localhost:8000/api/v1/auth/status \
  -H "Authorization: Bearer eyJhbGci..."
```

### Response — Authenticated

```json
{
  "authenticated": true,
  "user": "admin",
  "role": "admin"
}
```

### Response — Unauthenticated

```json
{
  "authenticated": false,
  "user": null
}
```

## Token Creation and Management

### JWT Token Structure

Tokens are created with the following claims:

```json
{
  "sub": "admin",
  "role": "admin",
  "exp": 1705402200,
  "iat": 1705302000
}
```

| Claim | Description |
|-------|-------------|
| `sub` | Subject (username) |
| `role` | Role: `admin` or `viewer` |
| `exp` | Expiration time (Unix epoch) |
| `iat` | Issued-at time (Unix epoch) |

### Token Creation (Internal)

Tokens are created using the `create_token()` function:

```python
def create_token(sub: str = "admin", role: str = "admin") -> str:
    exp = int(time.time()) + settings.jwt_expire_minutes * 60
    return jwt.encode(
        {"sub": sub, "role": role, "exp": exp, "iat": int(time.time())},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
```

### Token Expiry

Tokens expire after `JWT_EXPIRE_MINUTES` (default: 1440 minutes = 24 hours). There is no refresh token flow — clients should re-authenticate via `/api/v1/auth/login` when a token expires.

### Token Algorithm

The signing algorithm is configured via `JWT_ALGORITHM` (default: `HS256`). The secret key is `JWT_SECRET`.

> **Production security:** Change `JWT_SECRET` from the default value before deploying.

## Cookie-Based Session Auth

The web dashboard uses cookie-based authentication. When a user logs in via `/dashboard/login`, the dashboard sets a cookie:

```
Cookie: eco_guard_token=eyJhbGci...
```

The `verify_request()` middleware checks cookies in this order:

1. `Authorization: Bearer <token>` header
2. `eco_guard_token` cookie
3. `X-API-Key` header or `?api_key=` query param

### Using Cookies in API Calls

```bash
# Login and save the cookie
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin&password=admin" \
  -c cookies.txt

# Use the cookie in subsequent requests
curl http://localhost:8000/api/v1/predict \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello"}'
```

## API Key Authentication

API keys provide a simple authentication method for machine-to-machine communication.

### Using API Keys

```bash
# Via header (recommended)
curl -H "X-API-Key: eco-guard-dev-key" \
  http://localhost:8000/api/v1/predict \
  -d '{"prompt":"Hello"}'

# Via query parameter
curl "http://localhost:8000/api/v1/predict?api_key=eco-guard-dev-key" \
  -d '{"prompt":"Hello"}'
```

### API Key Management

API keys are configured via the `API_KEYS` environment variable:

```env
API_KEYS=["eco-guard-dev-key", "eco-guard-prod-key-1", "eco-guard-prod-key-2"]
```

The `APIKeyStore` class manages keys in memory:

```python
class APIKeyStore:
    def validate(self, key: str) -> bool:
        return key in self._keys

    def generate_key(self) -> str:
        key = f"eg-{secrets.token_urlsafe(32)}"
        self._keys.add(key)
        return key
```

Keys prefixed with `eg-` are generated with 32 bytes of urlsafe randomness for 43-character keys.

### API Key Auth Response

When authenticated via API key, the user context is:

```json
{
  "sub": "api-key",
  "role": "admin"
}
```

## Authentication Flow Diagrams

### Bearer Token Flow

```
Client                          Server
  │                                │
  │  POST /api/v1/auth/login       │
  │  username=admin&password=admin │
  │──────────────────────────────>│
  │                                │
  │  {"access_token":"eyJ...",     │
  │   "token_type":"bearer"}       │
  │<──────────────────────────────│
  │                                │
  │  POST /api/v1/predict           │
  │  Authorization: Bearer eyJ...  │
  │──────────────────────────────>│
  │                                │─── verify JWT signature
  │                                │─── check exp claim
  │                                │─── set request.state.user
  │  {"output":"Paris",...}        │
  │<──────────────────────────────│
```

### API Key Flow

```
Client                          Server
  │                                │
  │  POST /api/v1/predict           │
  │  X-API-Key: eco-guard-dev-key  │
  │──────────────────────────────>│
  │                                │─── check key in APIKeyStore
  │                                │─── set request.state.user
  │  {"output":"Paris",...}        │
  │<──────────────────────────────│
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_ENABLED` | `true` | Enable authentication globally. Set to `false` for development without auth. |
| `JWT_SECRET` | `"eco-guard-jwt-secret-change-in-production"` | HMAC secret key for signing JWT tokens |
| `JWT_ALGORITHM` | `"HS256"` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `1440` | Token lifetime in minutes (24 hours) |
| `ADMIN_USERNAME` | `"admin"` | Login username |
| `ADMIN_PASSWORD` | `"admin"` | Login password |
| `API_KEYS` | `["eco-guard-dev-key"]` | List of valid API keys (JSON array) |

## Disabling Authentication

For development or internal services, set `AUTH_ENABLED=false`:

```env
AUTH_ENABLED=false
```

When disabled, all requests pass through the `AuthMiddleware` without credential verification.
