# Change Log

This file records substantial project changes. Add new entries under
`Unreleased`; keep small formatting and comment-only edits out of the log.

## Unreleased
### Portfolio Analysis

- 2026-08-08: Added a strategy-level holdings table to the console PnL report
  and Streamlit holdings tabs. Amounts are summed by strategy, percentage
  returns are recalculated from aggregate amounts, and holding days use a
  market-value-weighted average. No persisted data schema changes. Validation:
  aggregation unit tests, Python syntax checks, and whitespace checks.


### Governance

- 2026-08-09: Added explicit approval boundaries for modifying or deleting
  existing files and project-folder hygiene rules that prohibit transient
  artifacts. Reduced mandatory operational-memory loading by selecting lessons
  by trigger instead of reading the growing reference in full. No runtime or
  data-schema impact. Validation: instruction checks, skill validation, and
  whitespace checks.

- 2026-08-08: Added mandatory project operational memory for reusing confirmed
  lessons from earlier failures. Initial lessons cover the canonical Yikai
  virtual-environment interpreter, sandbox escalation behavior, stale Streamlit
  processes, end-to-end consumer validation, and protected `.agents` writes.
  No runtime behavior or data migration impact. Validation: skill schema and
  mandatory-read path checks.

- 2026-08-08: Added mandatory repository coding-practice guidance covering
  architecture, error handling, testing, OOP, reuse, modularity, naming,
  readability, data integrity, and substantial-change logging. No runtime
  behavior or migration impact. Validation: skill schema validation and
  instruction-path checks.
