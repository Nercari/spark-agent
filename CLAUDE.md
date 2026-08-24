# Agent Guidelines & Repository Conventions

## Repository Overview
This repository implements the Gemini Spark Autonomous Learning Platform with engineering skill conventions.

## Documentation Structure
- `CONTEXT.md`: Root domain glossary and architecture model.
- `docs/adr/`: Architecture Decision Records.
- `docs/agents/`: Configuration for issue tracker, triage labels, and domain layouts.
- `.scratch/`: Local issue tracker and task tickets.

## Agent skills

When working on this repository, use the following engineering skills:

- `ask-matt`: Route engineering questions to the appropriate skill or practice.
- `domain-modeling`: Update and sharpen `CONTEXT.md` and `docs/adr/` when domain concepts or architectural decisions change.
- `grill-with-docs`: Stress-test technical designs against `CONTEXT.md` before implementation.
- `to-spec`: Transform discussions and requirements into structured specifications.
- `to-tickets`: Decompose specifications into vertical-slice task tickets in `.scratch/`.
- `triage`: Move tickets through canonical triage states (`needs-triage` -> `ready-for-agent`).
- `tdd`: Practice test-driven development (red-green-refactor) for implementation.
- `implement`: Execute tickets using disciplined TDD and pre-commit verification.
- `codebase-design`: Design deep modules with minimal interfaces and clean seams.
- `diagnosing-bugs`: Systematically diagnose and regression-test hard bugs.
- `code-review`: Review diffs for coding standards, code smells, and spec compliance.
