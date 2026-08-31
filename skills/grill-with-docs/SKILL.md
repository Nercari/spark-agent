---
name: grill-with-docs
description: Grilling session that challenges a plan against the domain model, sharpens terminology, and updates CONTEXT.md and ADRs inline as decisions crystallise. Use before implementing major features.
---
# Grill With Docs

Conduct an intensive interview to stress-test a proposed technical plan, resolve ambiguities, and record decisions in project documentation.

## When to Use

- Before starting work on complex features or architecture changes.
- When a plan or specification has unanswered questions, hidden assumptions, or unclear boundaries.

## Steps

1. **Review Existing Context**: Read `CONTEXT.md`, existing ADRs (`docs/adr/`), relevant code, and tests to understand established project language, constraints, and already-resolved facts.
2. **Structured Question Batteries**:
   - Group unresolved ambiguities into thematic batteries of questions (typically a cohesive cluster of 3–5 related questions per output, or fewer if only a minor set remains).
   - Group questions logically by subsystem, domain boundary, lifecycle stage, or dependency chain.
   - For each question within the battery:
     - State the specific context, edge case, data structure, or error path.
     - Present concrete options (e.g., Option A, Option B, Option C) with explicit trade-offs.
     - Provide a clear, justified recommended default based on existing project constraints.
     - Note the downstream architectural impact.
   - Await the user's response across the battery before progressing to the next thematic cluster.
3. **Resolve UI/UX Decisions**: If a decision is spatial or visual, offer a concrete mockup or prototype option.
4. **Persist Findings**:
   - Update `CONTEXT.md` with newly clarified terms and domain concepts.
   - Create ADRs in `docs/adr/` for significant trade-offs decided during the session.
5. **Next Route Recommendation**: When all material ambiguities and blocking decisions are resolved, explicitly recommend the appropriate follow-up workflow (e.g., `/to-spec` or `/to-tickets`).

## Gotchas

- Do not ask single isolated questions when multiple related decisions can be resolved together in a battery (unless only one isolated decision remains).
- Do not dump massive, unfocused lists (e.g., 10+ questions) across disparate topics; keep batteries cohesive and bounded to a handful of related questions.
- Never ask open-ended questions without concrete options, trade-offs, and a recommended default.
- If a question can be answered by exploring the existing codebase or documentation, inspect it directly instead of asking the user.
