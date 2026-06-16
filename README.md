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

### FastAPI middleware setup

```python
from fastapi import FastAPI
from omnibioai_security_sdk.core.config import SecurityConfig
from omnibioai_security_sdk.iam.client import IAMClient
from omnibioai_security_sdk.policy.client import PolicyClient
from omnibioai_security_sdk.middleware.auth import AuthMiddleware
from omnibioai_security_sdk.middleware.policy import PolicyMiddleware

app = FastAPI()

iam = IAMClient(SecurityConfig.IAM_BASE_URL, SecurityConfig.REDIS_URL)
policy = PolicyClient(SecurityConfig.POLICY_BASE_URL)

app.add_middleware(AuthMiddleware, iam=iam)
app.add_middleware(PolicyMiddleware, policy=policy)
```

Every request is now automatically:
- Authenticated (JWT validated via IAM client)
- Authorized (RBAC/ABAC decision via policy engine)
- Audited (event fired to Redis Streams)

### Fire an audit event

```python
from omnibioai_security_sdk.audit.client import fire_audit

fire_audit({
    "service": "my-service",
    "event_type": "data_access",
    "user_id": "123",
    "action": "GET /api/samples",
    "decision": "allow",
    "trace_id": "abc-123",
})
```

### S2S token validation

```python
from omnibioai_security_sdk.s2s.client import S2SClient

s2s = S2SClient(secret=SecurityConfig.SERVICE_SECRET)
token = s2s.generate(service="tes", audience="workbench")
valid = s2s.validate(token, expected_audience="workbench")
```

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

# 87% coverage
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

*Part of the [OmniBioAI](https://github.com/man4ish/omnibioai-studio) platform.*
