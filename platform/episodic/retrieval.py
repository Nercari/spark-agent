"""Episodic Retriever: Relevance-Scored & Route-Deduplicated Episodic Retrieval (EXP-02 & EXP-06)."""

from typing import List, Optional
from platform.episodic.backend import LocalFilesystemEpisodicBackend
from platform.episodic.contracts import EpisodicQuery, RetrievedEvidenceSubset
from platform.learning.contracts import TaskRunSummary, VerificationStatus, TaskRun


class EpisodicRetriever:
    """Retrieves relevant episodic summaries and bounded evidence subsets with relevance ranking and route deduplication."""

    def __init__(self, backend: Optional[LocalFilesystemEpisodicBackend] = None):
        self.backend = backend or LocalFilesystemEpisodicBackend()

    def _compute_relevance_score(self, summary: TaskRunSummary, query: EpisodicQuery) -> float:
        score = 0.0
        if query.user_goal_keywords:
            goal_tokens = set(summary.goal.lower().split())
            query_tokens = set(k.lower() for k in query.user_goal_keywords)
            overlap = len(goal_tokens & query_tokens)
            union = len(goal_tokens | query_tokens)
            score += (overlap / union) if union > 0 else 0.0

        if query.has_recovery is True and summary.has_recovery:
            score += 0.5

        if query.skill_name and summary.skill_name == query.skill_name:
            score += 0.2

        if query.verification_status and summary.verification_status == query.verification_status:
            score += 0.2

        return score

    def search_task_runs(self, query: EpisodicQuery) -> List[TaskRunSummary]:
        summaries = self.backend.list_summaries(project_scope_id=query.project_scope_id)
        filtered: List[TaskRunSummary] = []
        for s in summaries:
            if query.skill_name and s.skill_name != query.skill_name:
                continue
            if query.skill_version and s.skill_version != query.skill_version:
                continue
            if query.verification_status and s.verification_status != query.verification_status:
                continue
            if query.has_recovery is not None and s.has_recovery != query.has_recovery:
                continue
            filtered.append(s)

        scored = [(s, self._compute_relevance_score(s, query)) for s in filtered]
        scored.sort(key=lambda x: (x[1], x[0].has_recovery, x[0].timestamp), reverse=True)

        # Route-signature deduplication (EXP-06): group by route signature and retain best
        unique_results: List[TaskRunSummary] = []
        seen_route_signatures = set()

        for s, score in scored:
            route_sig = f"{s.skill_name}:{s.skill_version}:{s.has_recovery}:{s.verification_status.value}"
            if s.has_recovery:
                unique_results.append(s)
            elif route_sig not in seen_route_signatures:
                seen_route_signatures.add(route_sig)
                unique_results.append(s)

            if len(unique_results) >= query.limit:
                break

        return unique_results

    def get_progressive_evidence_subset(
        self,
        task_run_id: str,
        operation_id: Optional[str] = None,
    ) -> Optional[RetrievedEvidenceSubset]:
        task_run = self.backend.get_task_run(task_run_id)
        if not task_run:
            return None

        relevant_ops = []
        recovery_ev = None
        for ev in task_run.evidence_records:
            if operation_id is None or ev.operation_id == operation_id:
                relevant_ops.append({
                    "evidence_id": ev.evidence_id,
                    "tool_name": ev.tool_name,
                    "operation_id": ev.operation_id,
                    "attempt_id": ev.attempt_id,
                    "is_error": ev.is_error,
                    "is_recovery": ev.is_recovery,
                    "diff_summary": ev.diff_summary,
                })
            if ev.is_recovery and recovery_ev is None:
                recovery_ev = {
                    "evidence_id": ev.evidence_id,
                    "tool_name": ev.tool_name,
                    "operation_id": ev.operation_id,
                    "params": ev.params,
                    "diff_summary": ev.diff_summary,
                }

        summary_text = (
            f"TaskRun {task_run.id}: goal='{task_run.goal}', status={task_run.verification_status.value}, "
            f"recovery={task_run.has_recovery()}"
        )

        return RetrievedEvidenceSubset(
            task_run_id=task_run.id,
            goal=task_run.goal,
            verification_status=task_run.verification_status,
            had_recovery=task_run.has_recovery(),
            relevant_operations=relevant_ops,
            recovery_evidence=recovery_ev,
            summary_text=summary_text,
        )
