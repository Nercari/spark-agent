"""Episodic Memory Filesystem Backend implementation."""

import json
import os
import threading
from typing import Dict, List, Optional
from platform.learning.contracts import TaskRun, TaskRunSummary, VerificationStatus, generate_sha256
from platform.episodic.contracts import EpisodicQuery


class LocalFilesystemEpisodicBackend:
    """Thread-safe filesystem-based storage for TaskRuns, progressive evidence, and lightweight summaries."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.expanduser("~/.spark/episodic_evidence")
        self.summaries_dir = os.path.join(self.base_dir, "summaries")
        self.task_runs_dir = os.path.join(self.base_dir, "task_runs")
        self._lock = threading.Lock()
        os.makedirs(self.summaries_dir, exist_ok=True)
        os.makedirs(self.task_runs_dir, exist_ok=True)

    def save_task_run(self, task_run: TaskRun) -> str:
        """Saves a complete TaskRun and generates its lightweight summary."""
        with self._lock:
            # 1. Save full TaskRun
            task_run_path = os.path.join(self.task_runs_dir, f"{task_run.id}.json")
            with open(task_run_path, "w", encoding="utf-8") as f:
                json.dump(task_run.to_dict(), f, indent=2)

            # 2. Extract and save lightweight summary
            summary = task_run.to_summary()
            summary_path = os.path.join(self.summaries_dir, f"{task_run.id}.summary.json")
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary.to_dict(), f, indent=2)

            return task_run_path

    def get_task_run(self, task_run_id: str) -> Optional[TaskRun]:
        """Retrieves a full TaskRun by its ID."""
        task_run_path = os.path.join(self.task_runs_dir, f"{task_run_id}.json")
        if not os.path.exists(task_run_path):
            return None
        with open(task_run_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TaskRun.from_dict(data)

    def get_summary(self, task_run_id: str) -> Optional[TaskRunSummary]:
        """Retrieves a lightweight summary by TaskRun ID."""
        summary_path = os.path.join(self.summaries_dir, f"{task_run_id}.summary.json")
        if not os.path.exists(summary_path):
            return None
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TaskRunSummary.from_dict(data)

    def list_summaries(self, project_scope_id: Optional[str] = None) -> List[TaskRunSummary]:
        """Lists lightweight summaries across storage, optionally filtered by project scope."""
        results: List[TaskRunSummary] = []
        if not os.path.exists(self.summaries_dir):
            return results

        for filename in sorted(os.listdir(self.summaries_dir)):
            if filename.endswith(".summary.json"):
                summary_path = os.path.join(self.summaries_dir, filename)
                try:
                    with open(summary_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        summary = TaskRunSummary.from_dict(data)
                        if project_scope_id is None or summary.project_scope_id == project_scope_id:
                            results.append(summary)
                except Exception:
                    continue
        return results
