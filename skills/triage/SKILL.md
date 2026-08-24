---
name: user:triage
description: Move issues through a state machine of triage roles (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). Use when triaging issues and backlogs.
---
# Triage

Manage issue workflow states and transition issues through standard triage roles.

## When to Use

- When reviewing new issues, incoming bug reports, or feature requests.
- When assessing readiness of tasks for automated agent or human developer execution.

## Canonical Triage Roles

- `needs-triage`: Newly submitted issue awaiting initial review.
- `needs-info`: Requires additional reproduction steps, design decisions, or context.
- `ready-for-agent`: Fully specified, unambiguous task suitable for agent execution.
- `ready-for-human`: Requires human judgment, account credentials, physical actions, or external approvals.
- `wontfix`: Out of scope, duplicate, or rejected request.

## Steps

1. **Evaluate Issue Quality**: Check problem statement, reproduction steps, expected behavior, and acceptance criteria.
2. **Assess Complexity and Seams**: Determine if test seams and architecture boundaries are clear.
3. **Assign Triage Role**: Apply the appropriate label and provide concise reasoning.
4. **Request Clarifications**: If information is missing, ask specific questions to unblock the issue.

## Gotchas

- Only mark as `ready-for-agent` if the task has clear boundaries and acceptance criteria.
