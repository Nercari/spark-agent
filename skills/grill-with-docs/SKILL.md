---
name: user:grill-with-docs
description: Grilling session that challenges a plan against the domain model, sharpens terminology, and updates CONTEXT.md and ADRs inline as decisions crystallise. Use before implementing major features.
---
# Grill With Docs

Conduct an intensive interview to stress-test a proposed technical plan, resolve ambiguities, and record decisions in project documentation.

## When to Use

- Before starting work on complex features or architecture changes.
- When a plan or specification has unanswered questions, hidden assumptions, or unclear boundaries.

## Steps

1. **Review Existing Context**: Read `CONTEXT.md` and existing ADRs to understand established project language and constraints.
2. **Iterative Questioning (One at a Time)**:
   - Ask pointed questions about edge cases, data structures, error states, and UX flows.
   - For each question, propose a recommended answer with trade-offs.
   - Wait for the user's response before asking the next question.
3. **Resolve UI/UX Decisions**: If a decision is spatial or visual, offer a concrete mockup/prototype option.
4. **Persist Findings**:
   - Update `CONTEXT.md` with newly clarified terms.
   - Create ADRs in `docs/adr/` for significant trade-offs decided during the session.

## Gotchas

- Do not ask multiple complex questions in one turn.
- If a question can be answered by exploring the existing codebase, inspect the code directly instead of asking the user.
