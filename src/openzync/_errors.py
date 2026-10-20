"""Exception hierarchy matching the OpenZync API's RFC 7807 error responses.

Every API error is mapped to a typed exception so callers can handle
specific error conditions without inspecting raw response bodies.
"""

from __future__ import annotations

from typing import Any


class OpenZyncError(Exception):
    """Base exception for all OpenZync SDK errors."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "An unexpected error occurred."
    detail: dict[str, Any] | None = None

    def __init__(
        self,
        message: str | None = None,
        detail: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        if message is not None:
            self.message = message
        if detail is not None:
            self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(OpenZyncError):
    """Missing or invalid API key."""

    status_code: int = 401
    code: str = "authentication_error"
    message: str = "Authentication is required."


class AuthorizationError(OpenZyncError):
    """Authenticated but insufficient permissions."""

    status_code: int = 403
    code: str = "authorization_error"
    message: str = "You do not have permission to perform this action."


class NotFoundError(OpenZyncError):
    """Requested resource does not exist."""

    status_code: int = 404
    code: str = "not_found"
    message: str = "The requested resource was not found."


class ConflictError(OpenZyncError):
    """Resource already exists or is in a conflicting state."""

    status_code: int = 409
    code: str = "conflict"
    message: str = "The request conflicts with the current state of the resource."


class MethodNotAllowedError(OpenZyncError):
    """HTTP method not supported for this endpoint."""

    status_code: int = 405
    code: str = "method_not_allowed"
    message: str = "The HTTP method is not allowed for this endpoint."


class InternalServerError(OpenZyncError):
    """Server-side failure with no more specific mapping."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "The server encountered an unexpected error."


class PayloadTooLargeError(OpenZyncError):
    """Request body exceeds the maximum allowed size."""

    status_code: int = 413
    code: str = "payload_too_large"
    message: str = "The request body is too large."


class ValidationError(OpenZyncError):
    """Request payload failed validation."""

    status_code: int = 422
    code: str = "validation_error"
    message: str = "The request payload is invalid."


class RateLimitError(OpenZyncError):
    """Client exceeded rate-limit allowance."""

    status_code: int = 429
    code: str = "rate_limit_exceeded"
    message: str = "Too many requests. Please slow down."


class ExternalServiceError(OpenZyncError):
    """External dependency (LLM, DB, etc.) returned an error or timed out."""

    status_code: int = 502
    code: str = "external_service_error"
    message: str = "An external service error occurred."


class TransportError(OpenZyncError):
    """The request never reached the API, or the response could not be read.

    Raised for connection failures (refused, DNS, reset) and protocol
    errors — no HTTP response was received, so there is no status code
    from the API to report.  This is the counterpart of
    :class:`ExternalServiceError`: that one means the API *answered* with
    a 502, this one means the API never answered at all.
    """

    status_code: int = 503
    code: str = "transport_error"
    message: str = "The request could not reach the OpenZync API."


class RequestTimeoutError(TransportError):
    """The request timed out (connect, read, write, or pool timeout).

    A timeout is a distinct, retryable case within the transport family,
    so it keeps its own type and its own 504 status.
    """

    status_code: int = 504
    code: str = "request_timeout"
    message: str = "The request to the OpenZync API timed out."


class EntityNotFoundError(OpenZyncError):
    """Requested graph entity node does not exist."""

    status_code: int = 404
    code: str = "entity_not_found"
    message: str = "The requested entity was not found in the knowledge graph."


class GraphTimeoutError(OpenZyncError):
    """Graph database operation exceeded the configured timeout."""

    status_code: int = 504
    code: str = "graph_timeout"
    message: str = "The graph database operation timed out."


class CursorExpiredError(OpenZyncError):
    """Pagination cursor is malformed, stale, or from an older cursor version."""

    status_code: int = 400
    code: str = "cursor_expired"
    message: str = "The pagination cursor is invalid or expired."


class GoneError(OpenZyncError):
    """Resource is gone — used for hard-removed backends (e.g. postgres graph)."""

    status_code: int = 410
    code: str = "gone"
    message: str = "The requested resource is gone."


class ServiceUnavailableError(OpenZyncError):
    """A shared infrastructure component is unavailable (cache, DB, graph store)."""

    status_code: int = 503
    code: str = "service_unavailable"
    message: str = "A service dependency is unavailable."


class GraphBackendUnavailableError(ServiceUnavailableError):
    """Graph database backend cannot be reached."""

    status_code: int = 503
    code: str = "graph_backend_unavailable"
    message: str = "Graph database backend is unavailable."


class PIIUnavailableError(ServiceUnavailableError):
    """PII policy or redaction backend could not be reached (fail-closed)."""

    status_code: int = 503
    code: str = "pii_unavailable"
    message: str = "PII policy service is unavailable."


class LLMConfigurationError(OpenZyncError):
    """LLM backend cannot be resolved due to missing or invalid configuration."""

    status_code: int = 502
    code: str = "llm_configuration_error"
    message: str = "No LLM backend configured."


class EdgeNotFoundError(OpenZyncError):
    """Requested graph edge does not exist."""

    status_code: int = 404
    code: str = "edge_not_found"
    message: str = "The requested edge was not found in the knowledge graph."


# ── Error mapping ──────────────────────────────────────────────────────────

STATUS_TO_EXCEPTION: dict[int, type[OpenZyncError]] = {
    # 400 defaults to ValidationError: core emits `cursor_expired` only for
    # stale cursors, so a bad request without that code is a generic client
    # error. CursorExpiredError stays reachable via CODE_TO_EXCEPTION below.
    400: ValidationError,
    401: AuthenticationError,
    403: AuthorizationError,
    404: NotFoundError,
    405: MethodNotAllowedError,
    409: ConflictError,
    410: GoneError,
    413: PayloadTooLargeError,
    422: ValidationError,
    429: RateLimitError,
    500: InternalServerError,
    502: ExternalServiceError,
    503: ServiceUnavailableError,
    # No 504 entry: a 504 is GraphTimeoutError ONLY when the body code is
    # graph_timeout — any other 504 falls through to ServiceUnavailableError
    # (see raise_on_error), since 504s also come from non-graph paths.
}

# Machine-code dispatch table, checked before STATUS_TO_EXCEPTION. Core's
# RFC 7807 bodies carry the machine-readable code ONLY inside the `type` URL
# (`https://errors.openzync.tech/{code}`) — there is no top-level `code`
# field (see openzync-core/core/exceptions.py::_to_problem_json). Several
# codes share one HTTP status, so status alone cannot select the right
# subclass — e.g. 404 may be `not_found`, `entity_not_found`, or
# `edge_not_found`, and 503 may be `service_unavailable`,
# `graph_backend_unavailable`, or `pii_unavailable`. A matching code always
# wins over the status map.
ERRORS_TYPE_URL_PREFIX = "https://errors.openzync.tech/"
CODE_TO_EXCEPTION: dict[str, type[OpenZyncError]] = {
    "cursor_expired": CursorExpiredError,
    "authentication_error": AuthenticationError,
    "authorization_error": AuthorizationError,
    "not_found": NotFoundError,
    "entity_not_found": EntityNotFoundError,
    "edge_not_found": EdgeNotFoundError,
    "conflict": ConflictError,
    "method_not_allowed": MethodNotAllowedError,
    "internal_error": InternalServerError,
    "gone": GoneError,
    "payload_too_large": PayloadTooLargeError,
    "validation_error": ValidationError,
    "rate_limit_exceeded": RateLimitError,
    "external_service_error": ExternalServiceError,
    "llm_configuration_error": LLMConfigurationError,
    "service_unavailable": ServiceUnavailableError,
    "graph_backend_unavailable": GraphBackendUnavailableError,
    "pii_unavailable": PIIUnavailableError,
    "graph_timeout": GraphTimeoutError,
}


def _format_validation_errors(errors: list[dict[str, Any]]) -> str:
    """Flatten a FastAPI ``RequestValidationError`` detail list into one line.

    Args:
        errors: The ``detail`` list from a FastAPI 422 response, where each
            entry has ``loc`` (field path) and ``msg`` (failure reason).

    Returns:
        A single-line message like ``body.name: Field required``.
    """
    parts: list[str] = []
    for err in errors:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        msg = err.get("msg", "")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts)


def _resolve_code(body: dict) -> str | None:
    """Extract the machine-readable error code from a problem-json body.

    A real top-level ``code`` field wins (forward-compat if core ever adds
    one). Otherwise the code is derived from the ``type`` URL — the only
    place core puts it (``https://errors.openzync.tech/{code}``).

    Args:
        body: Parsed JSON response body.

    Returns:
        A code present in ``CODE_TO_EXCEPTION``, or ``None``.
    """
    code = body.get("code")
    if isinstance(code, str) and code in CODE_TO_EXCEPTION:
        return code
    type_url = body.get("type")
    if isinstance(type_url, str) and type_url.startswith(ERRORS_TYPE_URL_PREFIX):
        derived = type_url.rsplit("/", 1)[-1]
        if derived in CODE_TO_EXCEPTION:
            return derived
    return None


def raise_on_error(status_code: int, body: dict) -> None:
    """Map an RFC 7807 error response to the appropriate exception.

    Dispatch is code-first: when the body identifies a known machine-readable
    code — via a top-level ``code`` field or the ``type`` URL
    (``https://errors.openzync.tech/{code}``) — its exception wins regardless
    of HTTP status (several codes share one status). Otherwise the status map
    applies, or ``OpenZyncError`` as fallback.

    Args:
        status_code: HTTP status code.
        body: Parsed JSON response body (should contain ``detail``).

    Raises:
        The mapped ``OpenZyncError`` subclass, or ``OpenZyncError`` as fallback.
    """
    code = _resolve_code(body)
    if code is not None:
        exc_cls = CODE_TO_EXCEPTION[code]
    elif status_code == 504:
        # Graph-only: only a graph_timeout code earns GraphTimeoutError.
        # Any other 504 (proxy, upstream, non-graph path) is a generic
        # service timeout — typed as ServiceUnavailableError with the
        # real 504 status preserved on the instance.
        exc_cls = ServiceUnavailableError
    else:
        exc_cls = STATUS_TO_EXCEPTION.get(status_code, OpenZyncError)
    message = body.get("detail", exc_cls.message)
    # detail carries structured context only — title/type are RFC 7807
    # envelope (human label + code URL, already decoded via _resolve_code),
    # not error context, so they stay out.
    context: dict[str, Any] = {
        k: v for k, v in body.items() if k not in ("detail", "status", "title", "type")
    }
    if isinstance(message, list):
        # FastAPI RequestValidationError shape: [{"loc": ..., "msg": ...}].
        # Normalize to one readable line and keep the raw list on the
        # exception's detail so structured context is not lost.
        context["errors"] = message
        message = _format_validation_errors(message) or exc_cls.message
    raise exc_cls(
        message=message,
        detail=context,
        status_code=status_code,
    )
