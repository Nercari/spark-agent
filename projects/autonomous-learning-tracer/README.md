# Autonomous Learning Tracer Project

Demonstrates the complete Gemini Spark Hermes-compatible autonomous learning loop:

1. **Task Execution** under initial Skill `v1` (e.g. `structured-formatter`).
2. **Structured Evidence Capture** (`TaskRun`, `EvidenceEvent`).
3. **Explicit User Correction** (e.g. format constraint change).
4. **Background Reviewer Reflection** producing minimal targeted diff.
5. **Read-Before-Write Verification & Auto-Commit** of immutable version `v2`.
6. **Subsequent Equivalent Task** automatically retrieving `v2` and passing outcome verification without user intervention.
7. **Regression Detection & Autonomous Rollback** restoring `v2` if an invalid `v3` is encountered.
