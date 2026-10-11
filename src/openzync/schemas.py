"""Schemas domain client — admin extraction-schema management."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from openzync._errors import ValidationError
from openzync._http import AsyncHTTPTransport
from openzync.models.schema import (
    SchemaPreviewResponse,
    SchemaResponse,
    SchemaTemplateResponse,
)

# Mirrors core's CreateExtractionSchemaRequest.type pattern and
# schemas/sorting.py AdminSchemaSortBy/SortDir.
SchemaType = Literal["structured", "classification"]
AdminSchemaSortBy = Literal["name", "created_at"]
SortDir = Literal["asc", "desc"]


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
        schema_type: SchemaType = "structured",
    ) -> SchemaResponse:
        """Create an extraction schema from a Pydantic model.

        Derives the JSON Schema via ``model.model_json_schema()`` and
        registers it with ``POST /v1/admin/schemas``.

        Args:
            name: Display name for the schema (1-255 chars).
            model: Pydantic model class defining the extraction shape.
            prompt_template: Optional extraction prompt template.
            schema_type: Schema type — ``"structured"`` (default) or
                ``"classification"``. Sent as the wire field ``type``.

        Returns:
            ``SchemaResponse`` with the created schema.

        Raises:
            ValidationError: If ``name`` is empty or ``schema_type`` is
                not a known type (core would reject with 422).
        """
        if not name.strip():
            # ⚠️ BREAKING: was ValueError — now inside the OpenZyncError taxonomy
            raise ValidationError("name must be a non-empty string")
        if schema_type not in ("structured", "classification"):
            raise ValidationError(f"unknown schema type: {schema_type!r}")
        body: dict[str, Any] = {
            "name": name,
            "json_schema": model.model_json_schema(),
            "type": schema_type,
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
            ValidationError: If ``sample_text`` is empty.
        """
        if not sample_text.strip():
            # ⚠️ BREAKING: was ValueError — now inside the OpenZyncError taxonomy
            raise ValidationError("sample_text must be a non-empty string")
        data = await self._http.request(
            "POST",
            "/v1/admin/schemas/preview",
            json_body={
                "json_schema": model.model_json_schema(),
                "sample_text": sample_text,
            },
        )
        return SchemaPreviewResponse(**data)

    async def list(
        self,
        *,
        schema_type: SchemaType | None = None,
        is_active: bool | None = None,
        sort_by: AdminSchemaSortBy | None = None,
        sort_dir: SortDir = "desc",
    ) -> list[SchemaResponse]:
        """List schemas for the organization.

        Core returns an ``{"data", "total"}`` envelope — only ``data`` is
        surfaced here.

        Args:
            schema_type: Filter by schema type. Sent as the wire param
                ``type``. Omitted when None (no filtering).
            is_active: Filter by active status. Omitted when None.
            sort_by: Sort key. Omitted when None (backend default
                ``created_at``/``desc``).
            sort_dir: Sort direction; only sent alongside ``sort_by``.

        Returns:
            List of ``SchemaResponse`` models.
        """
        params: dict[str, str | int | bool] = {}
        if schema_type is not None:
            params["type"] = schema_type
        if is_active is not None:
            params["is_active"] = is_active
        if sort_by is not None:
            params["sort_by"] = sort_by
            params["sort_dir"] = sort_dir
        data = await self._http.request(
            "GET",
            "/v1/admin/schemas",
            params=params,
        )
        return [SchemaResponse(**item) for item in data["data"]]

    async def get(self, schema_id: str) -> SchemaResponse:
        """Get a single schema by ID.

        Args:
            schema_id: The UUID of the schema.

        Returns:
            ``SchemaResponse`` with the schema.
        """
        data = await self._http.request(
            "GET",
            f"/v1/admin/schemas/{schema_id}",
        )
        return SchemaResponse(**data)

    async def update(
        self,
        schema_id: str,
        *,
        name: str | None = None,
        json_schema: dict[str, Any] | None = None,
        prompt_template: str | None = None,
        is_active: bool | None = None,
    ) -> SchemaResponse:
        """Update an existing schema.

        The ``type`` field is immutable after creation and is not accepted
        here. Only provided fields are sent.

        Args:
            schema_id: The UUID of the schema to update.
            name: Optional new display name.
            json_schema: Optional new JSON Schema definition.
            prompt_template: Optional new prompt template.
            is_active: Optional new active status.

        Returns:
            ``SchemaResponse`` with the updated schema.
        """
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if json_schema is not None:
            body["json_schema"] = json_schema
        if prompt_template is not None:
            body["prompt_template"] = prompt_template
        if is_active is not None:
            body["is_active"] = is_active
        data = await self._http.request(
            "PUT",
            f"/v1/admin/schemas/{schema_id}",
            json_body=body,
        )
        return SchemaResponse(**data)

    async def delete(self, schema_id: str) -> None:
        """Soft-delete a schema (sets ``is_active`` to false).

        Args:
            schema_id: The UUID of the schema to delete.
        """
        await self._http.request(
            "DELETE",
            f"/v1/admin/schemas/{schema_id}",
        )

    async def templates(self) -> list[SchemaTemplateResponse]:
        """List the static starter schema templates.

        Returns:
            List of ``SchemaTemplateResponse`` models (``key``, ``name``,
            ``description``, ``json_schema``, ``sample_text``).
        """
        data = await self._http.request(
            "GET",
            "/v1/admin/schemas/templates",
        )
        return [SchemaTemplateResponse(**item) for item in data]
