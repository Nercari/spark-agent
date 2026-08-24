# Domain Documentation Layout

## Model
Single-context repository.

## Structure
- **Domain Glossary & Context**: Root `CONTEXT.md`.
- **Architecture Decision Records**: `docs/adr/` (formatted as `docs/adr/NNNN-<slug>.md`).
- **Agent Guidelines & Skill Routing**: `AGENTS.md` and `docs/agents/`.

## Maintenance Rules
1. Extract and sharpen domain terminology whenever new concepts are introduced.
2. Document architectural trade-offs in `docs/adr/`.
3. Keep `CONTEXT.md` focused on domain definitions, models, and boundaries.
