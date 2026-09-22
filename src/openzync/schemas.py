"""Schemas domain client — admin extraction-schema management."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from openzync._http import AsyncHTTPTransport
from openzync.models.schema import SchemaPreviewResponse, SchemaResponse


class AsyncSchemasClient:
    """Async client for admin extraction-schema endpoints.

    Args:
        http: The shared async HTTP transport instance.
    """

    def __init__(self, http: AsyncHTTPTransport) -> None:
        self._http = http

    async def create_from_pydantic(
        self,
        name: str,
        model: type[BaseModel],
        prompt_template: str | None = None,
    ) -> SchemaResponse:
        """Create an extraction schema from a Pydantic model.

        Derives the JSON Schema via ``model.model_json_schema()`` and
        registers it with ``POST /v1/admin/schemas``.

        Args:
            name: Display name for the schema (1-255 chars).
            model: Pydantic model class defining the extraction shape.
            prompt_template: Optional extraction prompt template.

        Returns:
            ``SchemaResponse`` with the created schema.

        Raises:
            ValueError: If ``name`` is empty.
        """
        if not name.strip():
            raise ValueError("name must be a non-empty string")
        body: dict[str, Any] = {
            "name": name,
            "json_schema": model.model_json_schema(),
        }
        if prompt_template is not None:
            body["prompt_template"] = prompt_template
        data = await self._http.request(
            "POST",
            "/v1/admin/schemas",
            json_body=body,
        )
        return SchemaResponse(**data)

    async def preview_from_pydantic(
        self,
        model: type[BaseModel],
        sample_text: str,
    ) -> SchemaPreviewResponse:
        """Preview extraction against sample text using a Pydantic model.

        Derives the JSON Schema via ``model.model_json_schema()`` and
        posts it with the sample to ``POST /v1/admin/schemas/preview``.

        Args:
            model: Pydantic model class defining the extraction shape.
            sample_text: Sample text to extract from.

        Returns:
            ``SchemaPreviewResponse`` with the extracted data preview.

        Raises:
            ValueError: If ``sample_text`` is empty.
        """
        if not sample_text.strip():
            raise ValueError("sample_text must be a non-empty string")
        data = await self._http.request(
            "POST",
            "/v1/admin/schemas/preview",
            json_body={
                "json_schema": model.model_json_schema(),
                "sample_text": sample_text,
            },
        )
        return SchemaPreviewResponse(**data)
