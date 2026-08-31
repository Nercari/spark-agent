# Project Context & Domain Model

## Project Overview
Gemini Spark Autonomous Learning Platform (Hermes-Compatible Implementation Baseline). An autonomous agent architecture designed to execute tasks with minimal supervision, preserve four-tier memory separation, learn reusable procedural skills, and perform self-healing and rollback on regression.

## Core Domain Terminology

- **Working Context**: Ephemeral task/conversation state available within the current live conversation/session and execution context. It is not automatically inherited by a genuinely fresh top-level conversation unless recovered from a persistent surface.
- **Declarative Memory (Bridge 1)**: Structured repository for persistent facts, user preferences, and scoped conventions (`MemoryRecord`, `memory.json`). Operates via single-active-record mutations per scope/type.
- **Episodic Evidence Capture (Bridge 2)**: Salience-gated historical record of non-trivial task executions, errors, recoveries, and verified outcomes. Stored in a dedicated native private skill surface (`episodes.json` JSON array).
- **Procedural Skill**: Versioned, progressively disclosed instructions (`SKILL.md` packages).
- **Authority Hierarchy**:
  1. Current Authoritative State (live remote API / system reality)
  2. Active Declarative Convention (`memory.json`)
  3. Applicable Procedural Skill (`SKILL.md`)
  4. Episodic Historical Evidence (`episodes.json`)
- **Episodic Attribution Metrics**:
  - **RETRIEVED**: The episode was loaded into live task context.
  - **USED**: The retrieved episode materially shaped the plan, tool choice, or execution route.
  - **HELPED**: Observable evidence demonstrates that using the episode prevented a prior failure or improved execution; otherwise `UNVERIFIED`.
- **Bridge 2 Validation Gates**:
  - **E1 (Natural Capture)**: Autonomous persistence of qualifying episode during natural task execution without explicit logging commands.
  - **E2 (Authoritative Read-Back & JSON Integrity)**: Direct native read-back confirming valid JSON array schema and descriptive semantics.
  - **E3 (Fresh Retrieval)**: Automatic relevant episode discovery in a clean session via `project_key` and `task_kind`.
  - **E4 (Evidence-Informed Use)**: Avoiding previously demonstrated failure on first attempt guided by retrieved evidence.

## Architectural Boundaries & Invariants

1. **Read-Before-Write**: Mutations must be evaluated against the current canonical active version.
2. **Reversibility**: Skill mutations append a new version; active version pointer switches only upon validation.
3. **Provenance Boundary**: External inputs (web, email, docs, MCP responses) remain evidence, never standing behavioral authority.
4. **Strict Descriptive Isolation**: Episodic records are historical case evidence only. They never serve as standing rules or direct procedural directives without formal promotion.
5. **Salience Gating**: Only non-trivial executions with errors, recoveries, material user corrections, or distinct multi-step routes are captured.
