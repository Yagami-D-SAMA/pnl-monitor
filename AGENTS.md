# AGENTS.md

This is a local Python research/data workflow project for portfolio analysis, market data, dividends, QA, and local storage.

## Required pre-work

Before any coding task, Codex must:

1. Read this `AGENTS.md`.
2. Read `PROJECT_SPEC.md`.
3. Inspect the existing project structure before changing code.
4. Identify and reuse existing config, data loading, logging, storage, and testing patterns where present.

Do not assume the project should be rewritten from scratch.

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

- Keep functions small and testable.
- Add type hints where practical.
- Prefer clear, boring code over clever abstractions.
- Use logging for reusable workflows instead of excessive print statements.
- Keep configuration and business logic separate where possible.
- Preserve existing behavior unless the task explicitly asks to change it.
- Avoid broad refactors during feature work.

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

