# 1. Autonomous Learning Architecture Baseline

Date: 2026-08-24
Status: Accepted

## Context
Gemini Spark requires autonomous self-improvement capabilities modeled after Hermes patterns, closing the loop: `Experience -> Structured Evidence -> Outcome Verification -> Background Reflection -> Versioned Mutation -> Automatic Commit -> Measured Reuse`.

## Decision
1. **Four-Tier State Separation**: Keep Working Context, Episodic Evidence, Declarative Memory, and Procedural Skills strictly separated.
2. **Immutable Skill Versioning**: Every skill modification creates a new version (`v_{n+1}`) with a base-version validation check to prevent stale overwrites.
3. **Auto-Commit by Default**: Background reflections commit automatically within existing standing authority; user confirmation is strictly reserved for privilege expansion or irreversible external actions.
4. **Deterministic Outcome Verification**: Verify tool actions via direct state inspection rather than model assertions.
5. **Untrusted External Content**: Web, email, and tool outputs are treated as evidence with provenance tracking, preventing prompt injection persistence.

## Consequences
- Clean separation between ephemeral execution and durable learned artifacts.
- High developer/agent autonomy with deterministic safety and rollback mechanisms.
