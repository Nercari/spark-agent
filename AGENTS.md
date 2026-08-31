# Repository Guidelines: Gemini Spark Autonomous Agent

## Project Structure & Architecture
- `platform/`: Autonomous self-learning core runtime (Hermes-compatible implementation baseline).
  - `learning/`: Procedural skill learning, reflection engine, and version store.
  - `memory/`: Declarative memory store and context management.
  - `episodic/`: Episodic evidence capture and retrieval backend.
  - `curator/`: Autonomous curator, lifecycle observer, and telemetry ledger.
- `skills/`: Versioned procedural skills packages (`SKILL.md`, `metadata.json`, `versions/`).
- `projects/`: Task-level operational integration and test projects.
- `eval_engine/`: Behavioral evaluation harness and test suites.
- `ledger/`: Autoresearch experiments ledger tracking champion progression.
- `tests/`: Platform regression tests and unit test suite.
