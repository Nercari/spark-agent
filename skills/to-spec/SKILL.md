---
name: user:to-spec
description: Synthesize current conversation context and codebase understanding into a structured feature specification and publish it to the issue tracker. Use when drafting a spec or PRD.
---
# To Spec

Synthesize discussed requirements, user stories, and architecture decisions into an actionable technical specification.

## When to Use

- After a planning or grilling session to formalize requirements.
- When transforming a conversation into an issue/ticket spec.

## Steps

1. **Synthesize Requirements**: Gather all decided features, constraints, domain terms, and test seams from the conversation.
2. **Explore Codebase Touchpoints**: Confirm relevant files, data models, and existing seams.
3. **Draft Specification Structure**:
   - **Problem Statement**: What problem is being solved and why.
   - **Proposed Solution**: High-level approach and user experience.
   - **User Stories and Acceptance Criteria**: Numbered, testable statements (`As a... I want to... So that...`).
   - **Testing Seams**: Defined boundaries where behavior will be verified.
   - **Out of Scope**: Explicit non-goals.
4. **Review and Publish**: Present to the user for validation and publish to the configured issue tracker with the `ready-for-agent` triage label.

## Gotchas

- Do not invent speculative requirements; stay faithful to agreed decisions.
