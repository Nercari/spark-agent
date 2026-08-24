---
name: user:domain-modeling
description: Actively build and sharpen a project's domain model, terminology, CONTEXT.md glossary, and Architecture Decision Records (ADRs). Use when clarifying domain terms or documenting architecture.
---
# Domain Modeling

Maintain alignment on domain language and architectural decisions across the codebase.

## When to Use

- When starting a new feature or clarifying ambiguous business terminology.
- When making non-trivial, hard-to-reverse architectural choices.
- When creating or updating `CONTEXT.md` or ADRs under `docs/adr/`.

## Steps

1. **Extract Domain Terms**: Identify nouns and verbs used by domain experts and users.
2. **Sharpen Terminology**: Eliminate synonyms and ambiguous phrasing; establish single canonical terms.
3. **Update CONTEXT.md**: Record domain definitions and relationships in `CONTEXT.md`.
4. **Document Architectural Decisions**:
   - Write an Architecture Decision Record (ADR) in `docs/adr/` when decisions involve trade-offs, are difficult to undo, or require shared context for future developers.
5. **Cross-Check with Code**: Ensure variable, function, and file naming match the domain glossary.

## Gotchas

- Do not use `CONTEXT.md` as an exhaustive implementation tracker; keep it focused on domain concepts and glossary.
