"""Tests for error mapping and HTTP error handling."""

from __future__ import annotations

import pytest
from httpx import Response

from openzync._errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    CursorExpiredError,
    EdgeNotFoundError,
    ExternalServiceError,
    GoneError,
    GraphTimeoutError,
    LLMConfigurationError,
    NotFoundError,
    OpenZyncError,
    PayloadTooLargeError,
    PIIUnavailableError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
    raise_on_error,
)

# Trusted host whose type-URL last segment is derived into a machine code.
ERRORS_TYPE_URL = "https://errors.openzync.tech"


class TestErrorMapping:
    """Tests for ``raise_on_error``."""

    def test_401_raises_authentication_error(self):
        with pytest.raises(AuthenticationError):
            raise_on_error(401, {"detail": "Missing auth"})

    def test_404_raises_not_found_error(self):
        with pytest.raises(NotFoundError):
            raise_on_error(404, {"detail": "Not found"})

    def test_429_raises_rate_limit_error(self):
        with pytest.raises(RateLimitError):
            raise_on_error(429, {"detail": "Too many requests"})

    def test_422_raises_validation_error(self):
        with pytest.raises(ValidationError):
            raise_on_error(422, {"detail": "Invalid input"})

    def test_custom_message(self):
        with pytest.raises(NotFoundError) as exc:
            raise_on_error(404, {"detail": "User not found", "user_id": "abc"})
        assert "User not found" in str(exc.value)

    def test_403_raises_authorization_error(self):
        with pytest.raises(AuthorizationError):
            raise_on_error(403, {"detail": "Forbidden"})

    def test_409_raises_conflict_error(self):
        with pytest.raises(ConflictError):
            raise_on_error(409, {"detail": "Conflict"})

    def test_413_raises_payload_too_large_error(self):
        with pytest.raises(PayloadTooLargeError):
            raise_on_error(413, {"detail": "Too large"})

    def test_502_raises_external_service_error(self):
        with pytest.raises(ExternalServiceError):
            raise_on_error(502, {"detail": "Upstream error"})

    def test_504_raises_graph_timeout_error(self):
        with pytest.raises(GraphTimeoutError):
            raise_on_error(504, {"detail": "Graph timeout"})

    def test_unknown_status_falls_back(self):
        with pytest.raises(OpenZyncError):
            raise_on_error(599, {"detail": "Unknown error"})

    def test_error_constructs_with_extra_detail(self):
        """Extra keys in body become detail dict."""
        with pytest.raises(NotFoundError) as exc:
            raise_on_error(404, {"detail": "Not found", "resource": "user"})
        assert exc.value.detail == {"resource": "user"}

    def test_openzync_error_custom_status(self):
        """OpenZyncError accepts custom status_code."""
        err = OpenZyncError(message="custom", status_code=418)
        assert err.status_code == 418
        assert str(err) == "custom"


class TestErrorDispatch:
    """Tests for the code-first error-dispatch contract.

    Dispatch order: top-level body ``code`` → trusted type-URL segment →
    HTTP status map. Several codes share one HTTP status, so status alone
    cannot select the right subclass.
    """

    def test_code_dispatch_edge_not_found(self):
        with pytest.raises(EdgeNotFoundError):
            raise_on_error(404, {"code": "edge_not_found"})

    def test_code_dispatch_cursor_expired(self):
        with pytest.raises(CursorExpiredError):
            raise_on_error(400, {"code": "cursor_expired"})

    def test_code_dispatch_pii_unavailable(self):
        with pytest.raises(PIIUnavailableError):
            raise_on_error(503, {"code": "pii_unavailable"})

    def test_code_dispatch_llm_configuration_error(self):
        with pytest.raises(LLMConfigurationError):
            raise_on_error(502, {"code": "llm_configuration_error"})

    def test_code_dispatch_graph_timeout(self):
        with pytest.raises(GraphTimeoutError):
            raise_on_error(504, {"code": "graph_timeout"})

    def test_type_url_derives_edge_not_found(self):
        with pytest.raises(EdgeNotFoundError):
            raise_on_error(404, {"type": f"{ERRORS_TYPE_URL}/edge_not_found"})

    def test_type_url_derives_cursor_expired(self):
        with pytest.raises(CursorExpiredError):
            raise_on_error(400, {"type": f"{ERRORS_TYPE_URL}/cursor_expired"})

    def test_type_url_derives_pii_unavailable(self):
        with pytest.raises(PIIUnavailableError):
            raise_on_error(503, {"type": f"{ERRORS_TYPE_URL}/pii_unavailable"})

    def test_type_url_unknown_segment_falls_back_to_status(self):
        with pytest.raises(ValidationError):
            raise_on_error(400, {"type": f"{ERRORS_TYPE_URL}/unknown_thing"})

    def test_type_url_foreign_host_falls_back_to_status(self):
        with pytest.raises(NotFoundError):
            raise_on_error(404, {"type": "https://other.example/x"})

    def test_code_wins_over_type_url(self):
        with pytest.raises(GoneError):
            raise_on_error(
                410, {"code": "gone", "type": f"{ERRORS_TYPE_URL}/edge_not_found"}
            )

    def test_status_fallback_404(self):
        with pytest.raises(NotFoundError):
            raise_on_error(404, {"detail": "Not found"})

    def test_status_fallback_400(self):
        with pytest.raises(ValidationError):
            raise_on_error(400, {"detail": "Bad request"})

    def test_status_fallback_503(self):
        with pytest.raises(ServiceUnavailableError):
            raise_on_error(503, {"detail": "Unavailable"})

    def test_status_fallback_410(self):
        with pytest.raises(GoneError):
            raise_on_error(410, {"detail": "Gone"})

    def test_422_list_detail_flattened(self):
        raw_errors = [
            {"loc": ["body", "name"], "msg": "Field required"},
            {"loc": ["body", "age"], "msg": "value is not a valid integer"},
        ]
        with pytest.raises(ValidationError) as exc:
            raise_on_error(422, {"detail": raw_errors})
        assert "body.name: Field required" in str(exc.value)
        assert "body.age: value is not a valid integer" in str(exc.value)
        assert exc.value.detail is not None
        assert exc.value.detail["errors"] == raw_errors


class TestHTTPRetry:
    """Tests for HTTP retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_429(self, async_client, mock_http):
        """429 status triggers retry, then succeeds."""
        # First call returns 429, second returns 200
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Response(429, json={"detail": "Rate limited"})
            return Response(
                200,
                json={
                    "id": "u1",
                    "external_id": "alice",
                    "name": "Alice",
                    "organization_id": "org-1",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "is_deleted": False,
                    "message_count": 0,
                    "fact_count": 0,
                    "session_count": 0,
                    "permissions": ["project:read", "project:write"],
                },
            )

        mock_http.get("/v1/users/u1").side_effect = handler

        user = await async_client.users.get("u1")
        assert user.name == "Alice"
        assert call_count == 2
