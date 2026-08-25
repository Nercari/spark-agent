"""Durable Episodic Storage with Progressive Storage Layout (Summary Index vs Full Runs)."""

import abc
import os
import json
from typing import List, Optional
from platform.learning.contracts import TaskRun
from platform.episodic.contracts import TaskRunSummary


class EpisodicBackend(abc.ABC):
    """Abstract interface for storing and querying historical TaskRun records."""

    @abc.abstractmethod
    def list_summaries(self) -> List[TaskRunSummary]:
        pass

    @abc.abstractmethod
    def get_task_run(self, task_run_id: str) -> Optional[TaskRun]:
        pass

    @abc.abstractmethod
    def save_task_run(self, task_run: TaskRun) -> None:
        pass


class LocalFilesystemEpisodicBackend(EpisodicBackend):
    """Filesystem-backed episodic storage with isolated index and full run directories."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.runs_dir = os.path.join(self.base_dir, "runs")
        self.index_path = os.path.join(self.base_dir, "summaries.jsonl")
        os.makedirs(self.runs_dir, exist_ok=True)

    def _get_path(self, task_run_id: str) -> str:
        return os.path.join(self.runs_dir, f"{task_run_id}.json")

    def list_summaries(self) -> List[TaskRunSummary]:
        summaries = []
        if not os.path.exists(self.index_path):
            return summaries

        with open(self.index_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    summaries.append(TaskRunSummary(
                        task_run_id=data["task_run_id"],
                        goal=data["goal"],
                        skill_name=data["skill_name"],
                        skill_version=data["skill_version"],
                        verification_status=data["verification_status"],
                        started_at=data["started_at"],
                        completed_at=data["completed_at"],
                        event_count=data["event_count"],
                        project_scope_id=data["project_scope_id"],
                        user_scope_id=data["user_scope_id"],
                    ))
        return summaries

    def get_task_run(self, task_run_id: str) -> Optional[TaskRun]:
        fpath = self._get_path(task_run_id)
        if not os.path.exists(fpath):
            return None
        with open(fpath, "r", encoding="utf-8") as f:
            return TaskRun.from_dict(json.load(f))

    def save_task_run(self, task_run: TaskRun) -> None:
        with open(self._get_path(task_run.id), "w", encoding="utf-8") as f:
            json.dump(task_run.to_dict(), f, indent=2)

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
        with open(self.index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(summary.to_dict()) + "\n")


class DurableSparkEpisodicBackend(LocalFilesystemEpisodicBackend):
    """Production episodic backend configured with durable private runtime storage."""

    def __init__(self, persistent_storage_dir: Optional[str] = None):
        default_dir = os.path.expanduser("~/.spark/episodic_evidence")
        base_dir = persistent_storage_dir or default_dir
        super().__init__(base_dir=base_dir)
