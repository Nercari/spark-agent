from __future__ import annotations
from typing import List, Optional
from platform.episodic.backend import EpisodicBackend
from platform.episodic.contracts import (
    EpisodicSearchQuery,
    TaskRunSummary,
    TaskRunDetail,
)

class EpisodicRetriever:
    """High-level episodic retrieval pipeline supporting progressive disclosure,
    project scope isolation, and route-signature deduplication."""

    def __init__(self, backend: EpisodicBackend):
        self._backend = backend

    def search_task_runs(
        self,
        query: EpisodicSearchQuery,
        project_scope: Optional[str] = None,
        deduplicate_routes: bool = True,
    ) -> List[TaskRunSummary]:
        """Search task execution runs matching the query, strictly enforcing project scope isolation
        and deduplicating identical routine execution routes when requested."""
        runs = self._backend.search_runs(query, project_scope=project_scope)
        if not deduplicate_routes:
            return runs

        # Route deduplication: key by skill_name + skill_version + had_recovery + verification_status
        deduped: List[TaskRunSummary] = []
        seen_routes = set()

        for run in runs:
            # If run has an active error recovery or failure, always preserve it as a distinct episode
            if run.had_recovery or run.verification_status != "VERIFIED":
                deduped.append(run)
                continue

            route_sig = f"{run.skill_name}:{run.skill_version}:{run.had_recovery}:{run.verification_status}"
            if route_sig not in seen_routes:
                seen_routes.add(route_sig)
                deduped.append(run)

        return deduped

    def get_run_detail(self, task_id: str) -> Optional[TaskRunDetail]:
        """Retrieve full details of a specific task run for progressive disclosure."""
        return self._backend.get_run_detail(task_id)

    def extract_evidence_subset(self, detail: TaskRunDetail, max_events: int = 5) -> List[dict]:
        """Extract a compact subset of events for low-overhead context injection."""
        if not detail or not detail.evidence_events:
            return []
        # Return most relevant events (errors, mutations, recovery attempts)
        salient = [
            e for e in detail.evidence_events
            if e.get("type") in ("error", "mutation", "recovery_attempt", "verification_failure")
        ]
        if not salient:
            salient = detail.evidence_events[:max_events]
        return salient[:max_events]
