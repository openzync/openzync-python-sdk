Document pagination guidance: bulk users should prefer `AsyncOpenZync` with `async for` over sync iteration, which drives each item through a per-item `asyncio.run()`.
