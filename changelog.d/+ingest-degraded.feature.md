Added `degraded: bool` and `degrade_reason: str | None` to `IngestMemoryResponse`, so callers can detect a partially-degraded ingest — old payloads without these fields still parse via defaults.
