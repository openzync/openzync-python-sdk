# scripts/

Developer tooling (never imported at runtime).

## `export_openapi.py` — SDK↔backend drift snapshot

No `openapi.json` is checked in. To review drift between the SDK and
`openzync-core`:

```bash
# 1. Boot core (it serves /openapi.json from the FastAPI app):
make dev   # inside openzync-core

# 2. Snapshot the schema into the SDK:
python scripts/export_openapi.py [--base-url http://localhost:8000]
```

This writes `src/openzync/_openapi.json`. Diff it against the SDK's
request/response models when core changes an endpoint contract.
