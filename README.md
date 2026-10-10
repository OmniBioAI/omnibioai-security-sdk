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
- **Audit integration** — `AuditClient` for Redis Streams logging
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

# Coverage figures from earlier dated runs are historical snapshots; run the
# command above to measure the current checkout.
# Covers: IAM client, policy client, cache, middleware, S2S auth
```

---

## Building the Cython Extensions

`setup.py` compiles `middleware/policy.py`, `middleware/s2s.py`,
`auth/service.py`, `policy/client.py`, `iam/client.py`, and
`iam/cache.py` to C extensions via Cython for IP protection.

```bash
python -m pip install -e .          # triggers the build via pyproject.toml
# or, for a local in-place build:
python setup.py build_ext --inplace
```

**Supported Cython version:** `>=3.2,<3.3` (pinned in `pyproject.toml`).
The committed `*.c` files were generated with Cython 3.2.5 — that's the
verified-reproducible baseline. Cython 3.3.0 produces a large diff
versus 3.2.5 output that has **not** been reviewed; don't bump past
3.2.x without regenerating and diffing all six `.c` files first.

**macOS:** `setup.py` previously failed on macOS with a multiprocessing
`spawn`/`BrokenProcessPool` error. The cause: `cythonize(nthreads=...)`
was invoked at module import time, so on `spawn`-based platforms
(macOS/Windows) each worker process re-imported `setup.py` as
`__main__` and re-triggered the same build recursively. The fix wraps
the `setup()` call in `if __name__ == "__main__":` — this is the
standard fix for top-level multiprocessing under `spawn`, and it
preserves parallel Cythonizing (`nthreads=os.cpu_count()`) on every
platform; it does not fall back to serial.

**Linux ARM64:** `build/lib.linux-aarch64-cpython-313/*.so`,
`build/temp.linux-aarch64-cpython-313/*.o`, and top-level
`auth/service.cpython-313-aarch64-linux-gnu.so` /
`iam/cache.cpython-313-aarch64-linux-gnu.so` are intentionally
committed to git as prebuilt artifacts for that platform. Don't delete
or regenerate-and-overwrite them as a side effect of a local build —
run `git status`/`git diff -- build/` after any `build_ext` invocation
to confirm they're untouched, since a plain `rm -rf build` before
rebuilding will delete them from your working tree (recoverable with
`git checkout -- build/`, but easy to do by accident).

**Generated-source maintenance:** the `.c` files are checked in, so
they must be regenerated and committed whenever the corresponding
`.py` source changes — including docstring-only edits, since Cython
embeds `.py` line numbers and source text into the `.c` output. A
regeneration check (diff the freshly-cythonized output against the
committed `.c`) should be run before merging any change to the six
modules above.

**Local artifact policy:** macOS build byproducts
(`*.cpython-*-darwin.so`, `build/lib.macosx-*/`, `build/temp.macosx-*/`,
`*.egg-info/`) are gitignored and must never be committed. They're
untracked by design — don't `git add -A` in this repo without checking
`git status` first.

**Python compatibility:** CI builds Python 3.10–3.13 on Linux
(`.github/workflows/ci.yml`). Locally on macOS, 3.11/3.12/3.13 are
commonly available via Homebrew/pyenv; always let CI be the source of
truth for versions you haven't personally built and tested.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `BrokenProcessPool` / spawn error during `build_ext` | `cythonize()` running at import time, not under `if __name__ == "__main__":` | Already fixed in `setup.py`; if you see this again, check nothing re-introduced top-level multiprocessing. |
| Regenerated `.c` differs from committed `.c` by more than line-number/docstring churn | Wrong Cython version, or a real source change wasn't accompanied by regeneration | Confirm `cython --version` is in `3.2.x`; if the diff is substantive, investigate before committing — don't promote blindly. |
| `git status` shows Linux `.so`/`.o` files as modified after a local build | `build/` was deleted or overwritten by a non-Linux build | `git checkout -- build/ <path>.so` to restore; avoid `rm -rf build` before building. |

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
| `omnibioai-security-audit` | Audit event consumer — `AuditClient` emits events for this stream path |
| `omnibioai-api-gateway` | Primary consumer of this SDK's middleware stack |
| `omnibioai-iam-client` | Async variant of the IAM client for high-throughput |

---

## License

Apache 2.0

---

*Part of the [OmniBioAI](https://github.com/OmniBioAI/omnibioai-studio) platform.*
