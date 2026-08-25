"""Progressive Episodic History Retriever (Metadata Index -> Evidence Subset -> Full TaskRun)."""

from typing import Any, Dict, List, Optional
from platform.learning.contracts import TaskRun, EvidenceEvent, EventType, VerificationStatus
from platform.episodic.contracts import TaskRunSummary, EpisodicQuery
from platform.episodic.backend import (
    EpisodicBackend,
    LocalFilesystemEpisodicBackend,
    DurableSparkEpisodicBackend,
)


class EpisodicRetriever:
    """Provides progressive disclosure over historical TaskRun evidence."""

    def __init__(
        self,
        backend: Optional[EpisodicBackend] = None,
        evidence_dir: Optional[str] = None,
    ):
        if backend:
            self.backend = backend
        elif evidence_dir:
            self.backend = LocalFilesystemEpisodicBackend(base_dir=evidence_dir)
        else:
            self.backend = DurableSparkEpisodicBackend()

    def search_task_runs(self, query: EpisodicQuery) -> List[TaskRunSummary]:
        summaries: List[TaskRunSummary] = []
        all_summaries = self.backend.list_summaries()

        for summary in all_summaries:
            if query.skill_name and summary.skill_name != query.skill_name:
                continue
            if query.project_scope_id and summary.project_scope_id != query.project_scope_id:
                continue
            status_val = summary.verification_status.value if hasattr(summary.verification_status, "value") else str(summary.verification_status)
            query_status_val = query.verification_status.value if hasattr(query.verification_status, "value") else str(query.verification_status) if query.verification_status else None
            if query_status_val and status_val != query_status_val:
                continue

            summaries.append(summary)
            if len(summaries) >= query.limit:
                break

        return summaries

    def get_task_run_evidence_subset(
        self,
        task_run_id: str,
        event_types: Optional[List[EventType]] = None,
        errors_only: bool = False,
        recoveries_only: bool = False,
    ) -> List[EvidenceEvent]:
        task_run = self.backend.get_task_run(task_run_id)
        if not task_run:
            return []

        subset = []
        for ev in task_run.evidence_events:
            if event_types and ev.event_type not in event_types:
                continue
            if errors_only and not ev.metadata.get("is_error", False):
                continue
            if recoveries_only and not ev.metadata.get("is_recovery", False):
                continue
            subset.append(ev)

        return subset

    def get_full_task_run(self, task_run_id: str) -> Optional[TaskRun]:
        return self.backend.get_task_run(task_run_id)
