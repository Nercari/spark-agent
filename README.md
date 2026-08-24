# Spark Agent Platform

Gemini Spark Autonomous Agent Platform — Hermes-Compatible Autonomous Learning Baseline.

## Repository Structure

```text
/
├── README.md
├── .gitignore
├── projects/      # Isolated Spark user projects (projects/<slug>/)
├── skills/        # Repository-managed Spark Skills (skills/<slug>/SKILL.md)
├── platform/      # Shared, reusable Spark agent infrastructure
│   └── learning/  # Autonomous learning subsystem (Hermes-compatible)
└── tests/         # Unit and integration tests for platform infrastructure
```

## Autonomous Learning Subsystem

The platform implements an experience-driven self-improvement loop:

1. **Task Execution & Structured Evidence:** Telemetry captured into `TaskRun` and `EvidenceEvent` structures.
2. **Outcome Verification:** Deterministic verification of actual task outcomes (`VERIFIED_SUCCESS`, `VERIFIED_FAILURE`).
3. **Background Reviewer (Reflection):** Formulates targeted patches against the active canonical skill version upon explicit user corrections or verified recoveries.
4. **Read-Before-Write & Auto-Commit:** Rejects stale writes and autonomously commits versioned skill updates (`v_{n+1}`) within standing authority.
5. **Autonomous Rollback:** Automatically reverts to prior working versions upon verified downstream regression.

## Running Tests

Run the platform test suite:

```bash
python3 -m unittest discover -s tests -v
```

Run project-specific tests:

```bash
python3 -m unittest discover -s projects/autonomous-learning-tracer/tests -v
```

## Current Implementation Status

- [x] Four-tier state separation contracts (`contracts.py`)
- [x] Structured evidence capture (`evidence_recorder.py`)
- [x] Deterministic outcome verifiers (`verifier.py`)
- [x] Immutable version store & rollback engine (`version_store.py`)
- [x] Hermes-style background reflection reviewer (`reviewer.py`)
- [x] Read-before-write gatekeeper & auto-commit engine (`commit_engine.py`)
- [x] End-to-end Vertical Slice 1 tracer project (`projects/autonomous-learning-tracer/`)
