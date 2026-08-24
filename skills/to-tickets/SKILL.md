---
name: user:to-tickets
description: Break down a plan, spec, or conversation into vertical-slice tracer-bullet tickets with explicit blocking edges. Use when decomposing specs into actionable task tickets.
---
# To Tickets

Decompose technical specifications and plans into independently verifiable, vertical-slice tickets.

## When to Use

- When breaking a large specification into discrete tasks for implementation.
- When sequencing tasks with dependency graphs and blocking edges.

## Steps

1. **Vertical Slicing**:
   - Break work into end-to-end slices across schema, backend, UI, and tests.
   - Avoid horizontal slicing (e.g. writing all database migrations first).
   - Ensure each slice is independently demonstrable and fits within a single execution session.
2. **Define Blocking Dependencies**:
   - Identify predecessor and successor dependencies for each ticket.
   - Mark unblocked tickets as ready for immediate development.
3. **Handle Wide Refactors (Expand-Contract)**:
   - For wide-blast-radius refactors, sequence as: (1) Expand (add new form), (2) Migrate call sites in batches, (3) Contract (deprecate/remove old form).
4. **Publish Tickets**: Write tickets to the configured issue tracker or local markdown files (`.scratch/`).

## Gotchas

- Avoid oversized tickets that bundle multiple unrelated concerns.
