# AGENTS.md

This is a local Python research/data workflow project for portfolio analysis, market data, dividends, QA, and local storage.

## Required pre-work

Before any coding task, Codex must:

1. Read this `AGENTS.md`.
2. Read `PROJECT_SPEC.md`.
3. Read `.agents/skills/coding-practice/SKILL.md` in full.
4. Read `.agents/skills/project-operational-memory/SKILL.md` in full, then read
   only the `references/lessons.md` entries whose triggers match the task.
5. Inspect the existing project structure before changing code.
6. Identify and reuse existing config, data loading, logging, storage, and testing patterns where present.

At the start of each coding task, state in the first work update that these
instructions were read. Do not edit code if any required instruction file is
missing or unreadable.

Before any task that books, appends, imports, corrects, or removes an investment
transaction, Codex must also read:

`.agents/skills/trade-booking/SKILL.md`

The trade-booking skill is mandatory. In particular, back up the original file
before every booking write and retain that backup until the user reviews the
updated file and explicitly authorizes deletion.

Do not assume the project should be rewritten from scratch.
## File change approval

- Before modifying or deleting any existing file in any folder, identify the
  exact path and planned change, then obtain explicit user approval.
- A user request that explicitly names a file or clearly bounded set of files
  and asks for the change counts as approval for that stated scope.
- Do not expand approval to adjacent files, cleanup, refactors, moves, or
  deletions. Ask separately before touching them.
- Never delete an existing file merely to tidy the workspace. Trade-ledger
  backups remain governed by the stricter trade-booking skill.

## Workspace hygiene

- Do not create intermediate, scratch, patch, debug, export, screenshot, or
  backup files inside the project unless they are requested deliverables.
- Use in-memory data, stdout, or the operating-system temporary directory for
  transient work.
- Prevent avoidable caches when practical. If a tool creates an unexpected
  artifact, report it and request approval before deleting it.
- Before finishing, inspect the changed-file list and ensure every newly created
  project file is intentional, clearly named, and part of the requested result.

## Working principles

- Keep changes small, incremental, and easy to review.
- Prefer extending existing modules over creating parallel implementations.
- Reuse existing portfolio-position loading logic before adding new loaders.
- Reuse existing ticker mapping, market data, storage, and report patterns where available.
- Do not rewrite the project from scratch.
- Do not introduce new frameworks, databases, schedulers, or heavy dependencies unless explicitly requested.
- Prefer local-first data storage.
- Store raw and processed tabular data as Parquet where practical.
- Use CSV only when manual review is useful or explicitly requested.
- Keep API-provider code isolated behind provider-like interfaces.
- Use `pathlib.Path` for new path handling where practical.
- Avoid hard-coded secrets and API keys.
- Do not commit `.env`, credentials, downloaded data, or generated cache files.

## Coding style

- Follow `.agents/skills/coding-practice/SKILL.md` for the detailed engineering
  workflow, error handling, testing, OOP, reuse, modularity, readability,
  naming, comments, and data-integrity standards.
- Follow `.agents/skills/project-operational-memory/SKILL.md` before running
  project commands and record newly confirmed project-specific lessons there.
- Keep functions small and testable.
- Add type hints where practical.
- Prefer clear, boring code over clever abstractions.
- Use logging for reusable workflows instead of excessive print statements.
- Keep configuration and business logic separate where possible.
- Preserve existing behavior unless the task explicitly asks to change it.
- Avoid broad refactors during feature work.

## Change log

- Update the root `CHANGELOG.md` under `Unreleased` for substantial changes.
- A substantial change alters user-visible behavior or workflow, persisted data
  semantics/schema, shared interfaces, dependencies/configuration, or coordinated
  behavior across multiple modules.
- Record the date, affected area, behavioral change, compatibility or migration
  notes, and tests run.
- Do not add changelog entries for formatting, typo, comment-only, or tiny
  internal changes that do not alter behavior.

## Data and storage rules

- Prefer local storage.
- Raw provider responses should be preserved when useful for auditability.
- Processed outputs should be saved as Parquet.
- Optional CSV exports may be added for manual inspection.
- Do not overwrite important raw data silently.
- Record enough metadata to understand data source, retrieval time, ticker, and date filtering.

## Testing rules

- Add or update tests for new reusable logic where practical.
- Unit tests should not require live external API calls by default.
- API failures should be handled gracefully where the workflow can continue.
- Prefer small deterministic fixtures for provider, QA, and calculation tests.

## Task sizing

If a task is too large or mixes multiple phases, stop and propose a smaller next step before implementing.

## Done response

Every task should end with:

1. Files changed.
2. How to run.
3. Tests run.
4. Assumptions.

