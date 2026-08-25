"""Progressive Episodic History Retriever (Metadata Summary -> Evidence Subset -> Full TaskRun)."""

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
        """Stage 1: Progressive disclosure — Returns compact metadata summaries only."""
        summaries: List[TaskRunSummary] = []
        all_runs = self.backend.list_task_runs()

        for task_run in all_runs:
            if query.skill_name and task_run.skill_name != query.skill_name:
                continue
            if query.project_scope_id and task_run.project_scope_id != query.project_scope_id:
                continue
            if query.verification_status and task_run.verification_status != query.verification_status:
                continue
            if query.has_error is not None:
                has_err = any(e.metadata.get("is_error", False) for e in task_run.evidence_events)
                if has_err != query.has_error:
                    continue
            if query.has_recovery is not None:
                has_rec = any(e.metadata.get("is_recovery", False) for e in task_run.evidence_events)
                if has_rec != query.has_recovery:
                    continue

            summary = TaskRunSummary(
                task_run_id=task_run.id,
                goal=task_run.goal,
                skill_name=task_run.skill_name,
                skill_version=task_run.skill_version,
                verification_status=task_run.verification_status,
                started_at=task_run.started_at,
                completed_at=task_run.completed_at,
                event_count=len(task_run.evidence_events),
                project_scope_id=task_run.project_scope_id,
                user_scope_id=task_run.user_scope_id,
            )
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
        """Stage 2: Progressive disclosure — Returns bounded evidence event subset."""
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
        """Stage 3: Progressive disclosure — Loads full TaskRun only when strictly requested."""
        return self.backend.get_task_run(task_run_id)
