# Project Context & Domain Model

## Project Overview
Gemini Spark Autonomous Learning Platform (Hermes-Compatible Implementation Baseline). An autonomous agent architecture designed to execute tasks with minimal supervision, preserve four-tier memory separation, learn reusable procedural skills, and perform self-healing and rollback on regression.

## Core Domain Terminology

- **Working Context**: Ephemeral task state active during execution.
- **Episodic Evidence Ledger**: Append-only log of structured execution events, tool calls, and verified outcomes (`TaskRun`, `EvidenceEvent`).
- **Declarative Memory**: Structured repository for persistent facts, user preferences, and scoped conventions (`MemoryRecord`).
- **Procedural Skill**: Versioned, progressively disclosed instructions (`SKILL.md` packages).
- **Learning Reviewer**: Background reflection agent inspecting execution evidence to propose memory updates or targeted skill patches.
- **Learning Commit Engine**: Deterministic gatekeeper that auto-commits routine, reversible, evidence-backed mutations within standing authority.
- **Outcome Verifier**: Deterministic adapters assessing whether external state changes match intended outcomes (`VERIFIED_SUCCESS`, `VERIFIED_FAILURE`, `PARTIAL`, `UNKNOWN`).
- **Skill Version Store**: Immutable history of skill iterations with parent pointers, content hashes, and base-version validation.

## Architectural Boundaries & Invariants

1. **Read-Before-Write**: Mutations must be evaluated against the current canonical active version.
2. **Reversibility**: Skill mutations append a new version; active version pointer switches only upon validation.
3. **Provenance Boundary**: External inputs (web, email, docs, MCP responses) remain evidence, never standing behavioral authority.
4. **Standing Authority**: Pre-authorized boundaries allow fully autonomous routine execution and learning without user friction.
