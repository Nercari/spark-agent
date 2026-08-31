# 2. Native Memory Bridge 2 — Episodic Evidence Capture

Date: 2026-08-26
Status: Accepted

## Context
Following the completion and freeze of Native Memory Bridge 1 (Declarative Conventions via native skill storage), Gemini Spark requires a native episodic memory mechanism (Bridge 2) to capture, persist, and retrieve actionable historical execution evidence across fresh sessions without external database dependencies, local filesystem assumptions in live turns, or context pollution.

## Decisions

### 1. Salience-Gated Capture Boundary
Autonomous episodic capture is restricted to executions that satisfy all three criteria:
1. Within an identified active project scope (e.g., `project_key: "github:Nercari/spark-agent"`).
2. Non-trivial execution involving tool calls, subagents, or multi-step execution (pure conversations and simple read-only lookups remain ephemeral).
3. Presence of a salience signal: observed error/recovery, material user correction, verified multi-step route, or distinct reusable route. Routine smooth successes are not persisted.

### 2. Dedicated Native Private Persistence Surface
- Episodic records are persisted in a dedicated private native Skill surface (`user:use-spark-agent-episodic-evidence` containing `episodes.json`).
- Storage Contract: Root value is a JSON array (`[]` at clean baseline). Each episode is a JSON object element in the array.
- Bridge 1's `apply-spark-agent-conventions` remains frozen and dedicated to declarative conventions.
- No dependency on `~/.spark/episodic_evidence`, Python runtime filesystem in live turns, public GitHub, Google Drive, or MCP. `platform/episodic/` serves as reference semantics and test oracle.

### 3. Minimal Bounded Episode Schema
Each episode record contains:
- `episode_id`: Unique identifier (e.g., `ep_...`).
- `occurred_at`: RFC 3339 / ISO 8601 offset-aware timestamp.
- `project_key`: Scoped project identifier.
- `task_kind`: Stable discriminator to enable structured indexing without relying solely on free-text goal similarity.
- `goal`: High-level user goal.
- `verification_status`: `VERIFIED_SUCCESS`, `VERIFIED_FAILURE`, `PARTIAL`, or `UNKNOWN`.
- `salience_reasons`: Array of reasons (e.g. `["ERROR_RECOVERY"]`).
- `signals`: Flags such as `had_error`, `had_recovery`, `had_user_correction`.
- `recovery`: Optional structured summary of `failed_route` and `successful_route` (or null/omitted if no failure).
- `artifact_refs`: List of generated or verified artifact references.
Raw tool dumps, hidden thoughts, large payloads, and credentials are strictly excluded.

### 4. Strict Descriptive Isolation & Authority Hierarchy
Episodic records are historical case evidence only. They cannot override active conventions or live facts.
The strict authority hierarchy is:
`Current Authoritative State > Active Declarative Convention > Applicable Procedural Skill > Episodic Historical Evidence`

### 5. Progressive Retrieval & Attribution Semantics
- Two-stage retrieval filtering by `project_key`, `task_kind`, and error/recovery signals; reads top 1–2 episodes.
- Explicit attribution tracking:
  - `RETRIEVED`: Episode read into context.
  - `USED`: Episode materially shaped route or plan.
  - `HELPED`: Observable evidence of failure avoidance or efficiency gain; otherwise `UNVERIFIED`.
- No self-referential ledger logging in Bridge 2.

### 6. Live Verification Gates (E1–E4)
- **E1 (Natural Capture)**: Autonomous capture during natural task execution with safe, reproducible recovery.
- **E2 (Authoritative Read-Back & JSON Integrity)**: Direct native read-back verifying valid JSON array format, schema conformance, and record integrity.
- **E3 (Fresh Retrieval)**: Automatic retrieval in a new session.
- **E4 (Evidence-Informed Use)**: Avoidance of previously observed failure route on the first attempt based on retrieved evidence while independently checking live state.

## Consequences
- Clean separation between declarative facts (Bridge 1) and episodic execution history (Bridge 2).
- Native cross-session durability within Spark platform primitives using supported JSON array storage.
- Deterministic, verifiable POC path ready for live execution.
