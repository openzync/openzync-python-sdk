Raise a clear SDK error directing callers to `AsyncOpenZync` when sync wrappers are invoked inside a running event loop, instead of the opaque `asyncio.run()` `RuntimeError`.
