# Autonomy Pilot 1: Real Work, Zero Learning Prompts

## Overview

Autonomy Pilot 1 evaluates whether the autonomous learning and curation architecture reduces repeated user intervention during ordinary Spark workloads without explicit user instructions to manage memory, skills, or telemetry.

## Key Design Principles

1. **Zero Learning Prompts**: No prompts contain "remember this", "update the skill", "call the curator", or "record telemetry". All learning, persistence, and curation happen autonomously through standard task lifecycle hooks.
2. **Fresh Session Isolation**: Workload runs across 3 distinct sessions where in-memory state is destroyed between sessions and durable truth is loaded strictly from persistent backends (SQLite and file version store).
3. **Separation of Workload and Safety Tests**: Normal autonomy metrics track ordinary user tasks, while intentional regression/rollback demonstrations run as isolated safety tests.

## Workload Structure

- **Session 1: Baseline Work & Convention Ingestion (Tasks 1–4)**
  - *Task 1*: Normal telemetry reporting naturally establishes `canonical_export_format = compact_json`.
  - *Task 2*: Repository tag inspection under baseline skill `v1`.
  - *Task 3*: Batch telemetry stream processing encounters non-transient schema error, successfully recovers via `validate_headers=True`, and automatically synthesizes/commits skill `v2`.
  - *Task 4*: Artifact generation completing Session 1.

- **Session 2: Fresh Session — Memory & Skill Reuse (Tasks 5–7)**
  - *Task 5*: Status artifact request without repeating format convention; automatically retrieves and uses `compact_json`.
  - *Task 6*: Batch telemetry processing on new dataset using learned skill `v2`; achieves direct success with 0 recoveries.
  - *Task 7*: User provides natural correction: "This project now uses jsonl for status artifacts." Atomically supersedes old memory and activates `jsonl`.

- **Session 3: Fresh Session — Episodic Query & Corrected Truth (Tasks 8–10)**
  - *Task 8*: Status export request uses updated active truth `jsonl`.
  - *Task 9*: Natural historical investigation query ("What happened during the batch telemetry run in session 1?"); retrieves Task 3 history via lightweight episodic summaries without manual TaskRun IDs.
  - *Task 10*: Final pilot summary generation.

- **Controlled Safety Test**:
  - Deploys temporary corrupted skill child `v3`.
  - Verifies that verified failure fires `CuratorTriggerPolicy` and performs automatic rollback to `v2`.

## Verified Autonomy Metrics

- **Tasks Total**: 10
- **Verified Successes**: 10
- **Verified Failures**: 0
- **User Corrections**: 1 (Task 7 format update)
- **Manual Developer Interventions**: 0
- **Recoveries Required**: 1 (Task 3 before learning; 0 after learning)
- **Repeated Failures**: 0
- **Learned Skill Reuses**: 1 (Task 6)
- **Declarative Memory Reuses**: 2 (Tasks 5 & 8)
- **Episodic Retrieval Uses**: 1 (Task 9)
- **Lifecycle Completeness**: 10/10 (100%)
- **User Intervention Rate**: 10.0%
- **Recovery Rate**: 10.0% (0% on post-learning workloads)
