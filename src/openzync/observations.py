"""Observations domain client — graph-topology analysis results."""

from __future__ import annotations

from openzync._http import AsyncHTTPTransport
from openzync.models.observation import ObservationListResponse


class AsyncObservationsClient:
    """Async client for read-only observation queries.

    Args:
        http: The shared async HTTP transport instance.
    """

    def __init__(self, http: AsyncHTTPTransport) -> None:
        self._http = http

    async def list(
        self,
        *,
        subject_entity_id: str | None = None,
        observation_type: str | None = None,
        limit: int = 50,
    ) -> ObservationListResponse:
        """List observations for a project with optional filters.

        Observations are read-only snapshots of graph-topology analysis
        computed by the background worker.

        Args:
            subject_entity_id: Optional filter by subject entity UUID.
            observation_type: Optional filter — co_occurrence,
                temporal_pattern, or behavioral_pattern.
            limit: Maximum results per page (1–200).

        Returns:
            ``ObservationListResponse`` with observations and total count.
        """
        pid = await self._http.resolve_project_id()
        params: dict[str, str | int] = {"limit": limit}
        if subject_entity_id is not None:
            params["subject_entity_id"] = subject_entity_id
        if observation_type is not None:
            params["observation_type"] = observation_type
        data = await self._http.request(
            "GET",
            f"/v1/projects/{pid}/observations",
            params=params,
        )
        return ObservationListResponse(**data)
