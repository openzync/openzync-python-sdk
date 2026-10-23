<p align="center"><img src="./.github/assets/banner.png" width="100%" alt="OpenZync"></p>

# OpenZync Python SDK

**Graph memory that survives production** — the typed client for it.

<p align="center">
  <a href="https://pypi.org/project/openzync/"><img src="https://img.shields.io/pypi/v/openzync" alt="PyPI"></a>
  <a href="https://pypi.org/project/openzync/"><img src="https://img.shields.io/pypi/dm/openzync" alt="Downloads"></a>
  <a href="https://github.com/openzync/openzync-python-sdk/actions/workflows/ci.yml"><img src="https://github.com/openzync/openzync-python-sdk/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="Apache 2.0">
</p>

Sync and async clients for [OpenZync](https://github.com/openzync/openzync-core): typed models,
automatic pagination, idempotency keys and LangChain integration over one HTTP transport.

[PyPI](https://pypi.org/project/openzync/) · [Docs](https://docs.openzync.tech/en/latest/domains/sdk_python.html) · [Core](https://github.com/openzync/openzync-core) · [MCP](https://github.com/openzync/openzync-mcp) · [Contact](mailto:rohnsha0@gmail.com)

## Install

`pip install openzync` — Python 3.11+, Apache 2.0.

## Quick start

```python
from openzync import OpenZync

client = OpenZync(api_key="oz_live_your_api_key_here")  # base_url defaults to http://localhost:8000

session = client.sessions.create(external_id="session-1")
resp = client.memory.ingest(
    messages=[{"role": "user", "content": "Hi, I am Alice from Acme Corp."}],
    session_id=session.external_id,
)
for hit in client.graph.search("Alice Acme Corp", types="episodes,facts"):
    print(hit["content"], hit.get("score"))
```

Ingestion is asynchronous — the call returns a job and enrichment lands moments later. `memory.ingest`
is **always** sent as `multipart/form-data`, even for text-only payloads; the API rejects JSON there.

## Async

```python
import asyncio
from openzync import AsyncOpenZync

async def main() -> None:
    async with AsyncOpenZync(api_key="...") as client:
        await client.memory.ingest(messages=[{"role": "user", "content": "Hi"}], session_id="session-1")

asyncio.run(main())
```

## Core surface

```python
client.memory.ingest(messages=[...], session_id="s1")   # episodes; idempotency key handled
client.memory.get_context(query="...")                  # context assembled for a prompt
client.facts.add(facts=[...], session_id="s1")          # subject → predicate → object
client.facts.retract(fact_id, reason="corrected")       # withdraw, keep the history
client.graph.search("query", types="episodes,facts")    # hybrid search
client.users.create(external_id="alice")                # users; list_iter() auto-paginates
```

`memory`, `facts`, `graph`, `sessions`, `users`, `projects`, `search` and four more domains cover
the API — every method is in the [SDK reference](https://docs.openzync.tech/en/latest/domains/sdk_python.html).

## Errors

```python
from openzync._errors import NotFoundError, RateLimitError

try:
    user = client.users.get("non-existent-id")
except NotFoundError:
    print("User not found")
except RateLimitError:
    print("Rate limited — slow down")
```

Every failure raises an `OpenZyncError` subclass mapped from the HTTP status; transport errors and
timeouts are separate classes, so you retry only what is safe.

## Pagination

`for user in client.users.list_iter():` fetches pages as it iterates (`async for` on the async client).

## LangChain

```bash
pip install "openzync[langchain]"
```

`OZChatMessageHistory` keeps a conversation in OpenZync and takes an `AsyncOpenZync` client:

```python
from openzync import AsyncOpenZync
from openzync.integrations.langchain import OZChatMessageHistory

client = AsyncOpenZync(api_key="...")
history = OZChatMessageHistory(session_id="session-1", client=client)
history.add_user_message("Hello!")
```

`OZMemory`, `OZGraphRetriever` and the graph/fact tools ship in the same extra — [full reference](https://docs.openzync.tech/en/latest/domains/sdk_python.html).

## Development

```bash
git clone https://github.com/openzync/openzync-python-sdk.git
cd openzync-python-sdk
pip install -e ".[dev]"
pytest          # HTTP mocked with respx
```

## License

Apache 2.0 — see [LICENSE](./LICENSE). If OpenZync is useful to you, a star helps others find it.
