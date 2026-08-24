---
name: user:implement
description: Build work described by a spec or tickets, driving TDD at pre-agreed seams and closing out with code review before committing. Use when implementing ready features or tickets.
---
# Implement

Execute the implementation of a specification or ticket using disciplined TDD and pre-commit verification.

## When to Use

- When implementing a feature ticket marked ready for development.
- When executing a spec or implementation plan.

## Steps

1. **Review Spec and Domain Context**: Check the ticket, user stories, acceptance criteria, and `CONTEXT.md`.
2. **Agree on Test Seams**: Identify the public interfaces and testing surfaces before writing code.
3. **Execute TDD Loop**:
   - Write a failing test for a vertical slice.
   - Write minimal implementation to make it pass.
   - Run typecheck and local unit/integration tests.
   - Repeat slice by slice.
4. **Run Full Verification**: Run the entire test suite and linter.
5. **Self-Review**: Review the diff against standards and spec requirements before final commit.

## Gotchas

- Do not skip straight to writing implementation without failing tests.
- Keep commits focused on the single ticket scope.
