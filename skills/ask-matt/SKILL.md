---
name: user:ask-matt
description: Ask which engineering skill or workflow fits your situation. A router over engineering skills to find the right tool or practice for code work.
---
# Ask Matt

Route engineering tasks, coding questions, and feature development to the most appropriate skill or workflow in the engineering skill suite.

## When to Use

- When unsure which engineering skill to use for a specific development task.
- When planning a feature or refactor and deciding the sequence of skills.
- When troubleshooting workflows or selecting between TDD, bug diagnosis, architecture reviews, or specification drafting.

## Steps

1. **Assess the Request**: Understand the user's immediate engineering goal (e.g., scoping, planning, writing tests, implementing, fixing a bug, refactoring, reviewing code).
2. **Map to Available Skills**:
   - For scoping and requirements: `grill-with-docs`, `domain-modeling`, `to-spec`.
   - For task decomposition: `to-tickets`, `wayfinder`.
   - For development and tests: `tdd`, `implement`.
   - For debugging and fixing: `diagnosing-bugs`, `resolving-merge-conflicts`.
   - For architecture and quality: `codebase-design`, `improve-codebase-architecture`, `code-review`.
   - For repository setup: `setup-matt-pocock-skills`.
   - For research and prototypes: `research`, `prototype`, `wizard`.
   - For issue queue management: `triage`.
3. **Recommend Next Step**: Provide the user with the single best skill to run next, explaining why it fits.

## Gotchas

- Do not attempt to run multiple complex workflows simultaneously; guide the user through the sequential engineering loop.
