Map HTTP 405 and 500 to dedicated SDK errors and restrict `GraphTimeoutError` to graph timeouts (other 504s map to `ServiceUnavailableError`); RFC7807 `title`/`type` no longer leak into `detail`.
