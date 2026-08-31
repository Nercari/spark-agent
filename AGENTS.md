# Spark Agent Autonomous Subsystem

Autonomous learning and memory runtime subsystem for Gemini Spark.

## Directory Structure
- `platform/`: Autonomous runtime subsystems.
  - `curator/`: Lifecycle observation, regression evaluation, and rollback policies.
  - `declarative/` (or `memory/`): Declarative conventions, user preferences, and atomic memory store.
  - `episodic/`: Progressive episodic retrieval and task run histories.
  - `learning/`: Procedural skill evolution, reflection, mutation reviewer, and version store.
- `skills/`: User and platform skill manifests and execution procedures.
- `eval_engine/`: Frozen behavioral benchmark suite and evaluation engine.
- `ledger/`: Historical experiments ledger (`experiments_ledger.json`).
- `tests/`: Automated unit and integration test suite.
