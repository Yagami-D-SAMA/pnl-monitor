---
name: coding-practice
description: Engineering and coding standards for every implementation, bug fix, refactor, review fix, test change, CLI change, Streamlit change, data workflow change, or Python module change in the Yikai Code repository. Use before inspecting or modifying code so changes follow the project's preferred style, architecture, error handling, testing, naming, readability, reuse, and change-log rules.
---

# Yikai Coding Practice

Apply these standards to every coding task in this repository.

## Engineering mindset

1. Understand behavior before editing. Trace the entry point, callers, data
   flow, side effects, persisted files, and existing tests.
2. Define the contract: inputs, outputs, invariants, units, date basis, failure
   modes, and user-visible behavior.
3. Choose the smallest change that fully solves the problem. Preserve unrelated
   behavior and user changes.
4. Consider edge cases before implementation, especially empty data, missing
   fields, duplicates, stale files, holidays, currencies, time zones, API limits,
   partial failures, and reruns.
5. Optimize for correctness and maintainability before cleverness or brevity.

## Existing architecture

- Reuse existing code before creating a parallel implementation.
- Keep loading and normalization in `DataLoader` or existing provider code.
- Keep portfolio calculations in `Calculator` or focused pure helpers.
- Keep workflow orchestration in `analyzer` and entry-point modules.
- Keep Streamlit rendering and UI-only state in Streamlit modules or helpers.
- Keep API-specific behavior behind provider-like interfaces.
- Do not move responsibilities across these boundaries without a clear reason.

## Reuse and modularity

- Search for an existing loader, mapping, transform, formatter, calendar helper,
  provider, or fixture before adding code.
- Extract shared logic for multiple real consumers or meaningful duplication.
  Do not create abstractions for a single trivial call.
- Separate pure calculations from file, network, console, and UI side effects.
- Keep functions focused and use guard clauses to reduce deep nesting.
- Pass dependencies and configuration explicitly. Avoid hidden global state.
- Preserve public signatures unless a contract change is required; update every
  caller and test when a contract changes.

## OOP guidance

- Use a class when behavior owns meaningful state, configuration, lifecycle, or
  a replaceable interface, such as a provider, loader, store, or calculator.
- Prefer composition over inheritance.
- Keep constructors lightweight and free of surprising network or file writes.
- Do not create classes that only group unrelated static methods. Use functions
  for stateless transformations.
- Keep provider interfaces narrow and normalize provider output at the boundary.

## Error handling

- Catch the narrowest useful exception where recovery or context can be added.
  Never use a bare `except` or silently swallow an error.
- Distinguish expected no-data from provider, parsing, or system failure. Never
  convert failure into a plausible zero or empty result without a clear warning.
- In per-ticker or per-row workflows, warn with identifying context and continue
  only when partial results remain valid.
- Fail fast when required inputs, schemas, invariants, or output integrity fail.
- Include operation, ticker/file/date/provider context in errors and logs.
- Preserve original causes with `raise ... from exc` when translating errors.
- Add bounded timeout, retry, and rate-limit handling for external APIs when the
  existing provider pattern supports it. Never retry validation errors blindly.
- Never expose secrets in logs, exceptions, test output, or code.

## Testing discipline

- Add a regression test for every fixed bug when practical.
- Test pure business logic independently from network, filesystem, and UI code.
- Keep unit tests deterministic and offline. Mock providers or use fixtures;
  gate live API tests behind an explicit environment flag.
- Cover relevant boundaries: empty data, missing columns, duplicates, invalid
  types, API failure, date boundaries, holidays, currency/price units, and reruns.
- Scale tests to risk. Run broader tests when shared interfaces, loaders,
  calculations, or workflows change.
- Run syntax checks, relevant tests, a minimal end-to-end or UI smoke test when
  applicable, and `git diff --check` before completion.
- If a test cannot run, report why and what remains unverified.

## Readability and naming

- Follow repository conventions and PEP 8 where they do not conflict.
- Use `snake_case` for functions and variables, `PascalCase` for classes, and
  `UPPER_SNAKE_CASE` for constants.
- Choose domain names and include units or basis where ambiguity matters, such
  as `price_gbp`, `return_bps`, `as_of_date`, or `lookback_days`.
- Add type hints to new or changed reusable functions where practical.
- Keep comments concise and explain why, assumptions, or constraints. Do not
  narrate obvious syntax or leave stale commented-out code.
- Use short docstrings for public or non-obvious functions. Document units,
  side effects, and errors when unclear from the signature.
- Prefer readable intermediate variables over dense expressions.

## Finance and data integrity

- Make observation, running, retrieval, and available-as-of dates explicit.
  Avoid look-ahead bias.
- Make currencies, percentages, basis points, price scaling, and signs explicit.
- Do not silently forward-fill, substitute a source, or change ticker mappings
  unless required and documented.
- Preserve raw inputs and follow the trade-booking skill for ledger changes.
- Validate schemas and output cardinality before writing important local data.

## Change management

- Review `git status` and the relevant diff before editing. Treat unknown changes
  as user-owned and do not revert them.
- Implement substantial changes in reviewable increments and verify each step.
- Update root `CHANGELOG.md` under `Unreleased` for a substantial change. This
  means user-visible behavior/workflow, persisted schema or data semantics, a
  shared interface, dependencies/config, or coordinated multi-module behavior.
- Record date, area, behavior, compatibility or migration notes, and tests run.
  Skip typo, formatting, comment-only, or tiny no-behavior-change entries.

## Completion checklist

1. Re-read the request and verify every requirement.
2. Review the final diff for scope, debug code, secrets, and generated files.
3. Run proportionate tests and checks.
4. Update `CHANGELOG.md` when the change is substantial.
5. Report files changed, how to run, tests, assumptions, and unresolved risks.
