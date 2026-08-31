from __future__ import annotations
import json
import os
from abc import ABC, abstractmethod
from typing import List, Optional
from platform.episodic.contracts import (
    EpisodicSearchQuery,
    TaskRunSummary,
    TaskRunDetail,
)

class EpisodicBackend(ABC):
    """Abstract interface for episodic evidence storage and search."""

    @abstractmethod
    def search_runs(
        self,
        query: EpisodicSearchQuery,
        project_scope: Optional[str] = None,
    ) -> List[TaskRunSummary]:
        pass

    @abstractmethod
    def get_run_detail(self, task_id: str) -> Optional[TaskRunDetail]:
        pass

    @abstractmethod
    def record_run(self, detail: TaskRunDetail) -> None:
        pass


class LocalFilesystemEpisodicBackend(EpisodicBackend):
    """Filesystem-backed implementation of EpisodicBackend."""

    def __init__(self, base_dir: str = ".learning/evidence"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def record_run(self, detail: TaskRunDetail) -> None:
        file_path = os.path.join(self.base_dir, f"{detail.task_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(detail.to_dict(), f, indent=2)

    def get_run_detail(self, task_id: str) -> Optional[TaskRunDetail]:
        file_path = os.path.join(self.base_dir, f"{task_id}.json")
        if not os.path.isfile(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return TaskRunDetail.from_dict(data)
        except Exception:
            return None

    def search_runs(
        self,
        query: EpisodicSearchQuery,
        project_scope: Optional[str] = None,
    ) -> List[TaskRunSummary]:
        results: List[TaskRunSummary] = []
        if not os.path.isdir(self.base_dir):
            return results

        for filename in os.listdir(self.base_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.base_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                detail = TaskRunDetail.from_dict(data)

                # Project scope isolation
                if project_scope is not None and detail.project_scope != project_scope:
                    continue
                if query.project_scope is not None and detail.project_scope != query.project_scope:
                    continue

                # Query filtering
                if query.skill_name and detail.skill_name != query.skill_name:
                    continue
                if query.goal_substring and query.goal_substring.lower() not in detail.goal.lower():
                    continue
                if query.verification_status and detail.verification_status != query.verification_status:
                    continue
                if query.requires_recovery is not None and detail.had_recovery != query.requires_recovery:
                    continue

                summary = TaskRunSummary(
                    task_id=detail.task_id,
                    goal=detail.goal,
                    skill_name=detail.skill_name,
                    skill_version=detail.skill_version,
                    verification_status=detail.verification_status,
                    had_recovery=detail.had_recovery,
                    timestamp=detail.timestamp,
                    project_scope=detail.project_scope,
                )
                results.append(summary)
            except Exception:
                continue

        # Sort newest first
        results.sort(key=lambda s: s.timestamp or 0, reverse=True)
        if query.limit:
            results = results[:query.limit]
        return results
