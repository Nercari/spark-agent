---
name: user:setup-matt-pocock-skills
description: Configure repository infrastructure for engineering skills. Issue tracker (GitHub, GitLab, local markdown), triage labels, and domain doc layout (CONTEXT.md, docs/adr/). Run once per repo.
---
# Setup Matt Pocock Skills

Initialize and configure project repository documentation and issue tracking conventions required by the engineering skill suite.

## When to Use

- When setting up a repository for the first time with engineering skills.
- When configuring project conventions for issue tracking, triage labels, or domain documentation.

## Steps

1. **Explore the Repository**:
   - Check git remotes (`git remote -v`) to detect GitHub or GitLab remotes.
   - Check for existing documentation (`AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, `docs/adr/`, `docs/agents/`).
   - Check if repository is a monorepo (e.g. `pnpm-workspace.yaml`, `packages/*`).
2. **Select Issue Tracker**:
   - Propose GitHub Issues, GitLab Issues, or Local Markdown (`.scratch/`).
   - Record configuration in `docs/agents/issue-tracker.md`.
3. **Configure Triage Labels**:
   - Set up the canonical triage roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`).
   - Record in `docs/agents/triage-labels.md`.
4. **Establish Domain Doc Layout**:
   - Single-context (root `CONTEXT.md` + `docs/adr/`) for standard repos.
   - Multi-context (`CONTEXT-MAP.md` + package-level docs) for monorepos.
   - Record in `docs/agents/domain.md`.
5. **Update Root Agent Instructions**:
   - Add the `## Agent skills` block to `CLAUDE.md` or `AGENTS.md`.

## Gotchas

- Do not overwrite existing custom project conventions; update in-place without duplicating sections.
