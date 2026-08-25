"""Durable Episodic Storage Backend Abstraction."""

import abc
import os
import json
from typing import List, Optional
from platform.learning.contracts import TaskRun


class EpisodicBackend(abc.ABC):
    """Abstract interface for storing and querying historical TaskRun records."""

    @abc.abstractmethod
    def list_task_runs(self) -> List[TaskRun]:
        pass

    @abc.abstractmethod
    def get_task_run(self, task_run_id: str) -> Optional[TaskRun]:
        pass

    @abc.abstractmethod
    def save_task_run(self, task_run: TaskRun) -> None:
        pass


class LocalFilesystemEpisodicBackend(EpisodicBackend):
    """Filesystem-backed episodic storage."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_path(self, task_run_id: str) -> str:
        return os.path.join(self.base_dir, f"{task_run_id}.json")

    def list_task_runs(self) -> List[TaskRun]:
        results = []
        if not os.path.exists(self.base_dir):
            return results

        for fname in os.listdir(self.base_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.base_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            results.append(TaskRun.from_dict(data))
        return results

    def get_task_run(self, task_run_id: str) -> Optional[TaskRun]:
        fpath = self._get_path(task_run_id)
        if not os.path.exists(fpath):
            return None
        with open(fpath, "r", encoding="utf-8") as f:
            return TaskRun.from_dict(json.load(f))

    def save_task_run(self, task_run: TaskRun) -> None:
        with open(self._get_path(task_run.id), "w", encoding="utf-8") as f:
            json.dump(task_run.to_dict(), f, indent=2)


class DurableSparkEpisodicBackend(LocalFilesystemEpisodicBackend):
    """Production episodic backend configured with durable private runtime storage."""

    def __init__(self, persistent_storage_dir: Optional[str] = None):
        default_dir = os.path.expanduser("~/.spark/episodic_evidence")
        base_dir = persistent_storage_dir or default_dir
        super().__init__(base_dir=base_dir)
