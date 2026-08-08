# omnibioai-security-sdk

**Unified zero-trust security SDK for the OmniBioAI platform.**

Provides IAM token validation, service-to-service authentication,
policy enforcement, and audit event streaming as reusable components
for all OmniBioAI services.

---

## What It Provides

- **IAM client** — JWT validation with Redis caching (sub-ms fast path)
- **Policy client** — RBAC/ABAC evaluation via policy-engine
- **S2S authentication** — signed service tokens with audience validation
- **Audit integration** — `fire_audit()` helper for Redis Streams logging
- **FastAPI middleware** — drop-in auth + policy middleware stack

---

## Architecture

```
Incoming Request

↓

AuthMiddleware (SDK)

↓

IAMClient.validate(token)

↓

Redis cache hit → User context (0.3ms)

Redis cache miss → POST /auth/validate → cache + return

↓

PolicyMiddleware (SDK)

↓

PolicyClient.evaluate(user, action, resource)

↓

POST /policy/evaluate → allow/deny

↓

fire_audit(event) → Redis Streams (async, never blocks)
```

---

## Installation

```bash
# From the OmniBioAI ecosystem
pip install -e ~/Desktop/machine/omnibioai-security-sdk

# Or via pip (internal package)
pip install omnibioai-security-sdk
```

---

## Usage

> **Package layout note:** there is no `omnibioai_security_sdk/` package
> directory — the repo exposes its modules directly at the root
> (`iam/`, `policy/`, `audit/`, `core/`, `middleware/`, `auth/`), and
> `pip install omnibioai-security-sdk`/`-e .` installs them at that
> top level, importable as e.g. `from iam.client import IAMClient`.
> **`middleware/auth.py` and `middleware/policy.py` internally import
> from `omnibioai_security_sdk.*`** (a package that doesn't exist under
> that name) — this is a real, currently-unresolved issue, not a doc
> typo: `tests/test_middleware.py`'s own docstring documents working
> around it by wiring `sys.modules` before import. Until that's fixed,
> `AuthMiddleware`/`PolicyMiddleware` will raise `ModuleNotFoundError`
> on a normal import from a consuming service. `middleware/s2s.py` and
> everything under `iam/`, `policy/`, `audit/` do **not** have this
> problem — they're plain, working imports.

### IAM + Policy clients (working today)

```python
from fastapi import FastAPI
from iam.client import IAMClient
from policy.client import PolicyClient

app = FastAPI()

iam = IAMClient(base_url="http://omnibioai-auth:8001", redis_url="redis://redis:6379")
policy = PolicyClient(base_url="http://omnibioai-policy-engine:8001")

user = await iam.validate(token)
decision = await policy.evaluate(user, action="GET /api/samples", resource="samples")
```

(`AuthMiddleware`/`PolicyMiddleware` wrap this same pattern as FastAPI
middleware — see the package-layout note above before depending on them
as installed.)

### Fire an audit event

There is no bare `fire_audit()` function — `audit/client.py` exposes an
`AuditClient` class:

```python
from audit.client import AuditClient

audit = AuditClient(redis_url="redis://redis:6379")

await audit.emit({
    "service": "my-service",
    "event_type": "data_access",
    "user_id": "123",
    "action": "GET /api/samples",
    "decision": "allow",
    "trace_id": "abc-123",
})
```

### S2S request authentication

`middleware/s2s.py` is a FastAPI/Starlette middleware
(`ServiceAuthMiddleware`), not a standalone client with `generate()`/
`validate()` methods — it only verifies an incoming `X-Service-Token`
header against a shared HS256 secret and checks the token's `aud` claim
names this service:

```python
from middleware.s2s import ServiceAuthMiddleware

app.add_middleware(
    ServiceAuthMiddleware,
    secret=SecurityConfig.SERVICE_SECRET,
    service_name="workbench",
)
```

A request without a valid `X-Service-Token` (signed by the caller,
`aud` including `"workbench"`) gets `401`/`403`. Generating that token
in the first place is the caller's own responsibility — this repo has
no token-issuance code for S2S tokens today.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `IAM_BASE_URL` | `http://omnibioai-auth:8001` | Auth service URL |
| `POLICY_BASE_URL` | `http://omnibioai-policy-engine:8001` | Policy engine URL |
| `REDIS_URL` | `redis://redis:6379` | Redis for token cache |
| `SERVICE_SECRET` | — | S2S token signing secret |

---

## Testing

```bash
cd ~/Desktop/machine/omnibioai-security-sdk
pytest tests/ -v --cov=.

# 95% coverage (verified 2026-08-07; 72 tests)
# Covers: IAM client, policy client, cache, middleware, S2S auth
```

---

## Design Principles

- **Zero trust** — every request authenticated, authorized, audited
- **Fail closed** — auth/policy failures return 401/403, never pass through
- **Fail open on audit** — audit errors never block requests
- **Cache-first** — Redis cache checked before any network call
- **HPC-safe** — non-blocking async design for high-throughput workloads

---

## Related Services

| Service | Role |
|---------|------|
| `omnibioai-auth` | JWT issuance — IAM client validates against this |
| `omnibioai-policy-engine` | RBAC/ABAC decisions — policy client calls this |
| `omnibioai-security-audit` | Audit event consumer — fire_audit() writes here |
| `omnibioai-api-gateway` | Primary consumer of this SDK's middleware stack |
| `omnibioai-iam-client` | Async variant of the IAM client for high-throughput |

---

## License

Apache 2.0

---

*Part of the [OmniBioAI](https://github.com/OmniBioAI/omnibioai-studio) platform.*
