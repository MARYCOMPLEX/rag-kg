"""RoutedRAGPlanner — dispatches to a local or global sub-planner via QueryRouter."""

from __future__ import annotations

from packages.core.models import Query
from packages.retrieval.protocols import RetrievalPlanner, RetrievalResult
from packages.retrieval.router import QueryRouter


class RoutedRAGPlanner:
    """Delegates each query to either the local or global planner based on routing."""

    def __init__(
        self,
        *,
        router: QueryRouter,
        local_planner: RetrievalPlanner,
        global_planner: RetrievalPlanner,
    ) -> None:
        self._router = router
        self._local_planner = local_planner
        self._global_planner = global_planner

    async def plan_and_retrieve(
        self,
        library_id: str,
        query: Query,
    ) -> RetrievalResult:
        decision = self._router.classify(query.text)
        chosen = self._global_planner if decision.route == "global" else self._local_planner
        return await chosen.plan_and_retrieve(library_id, query)
