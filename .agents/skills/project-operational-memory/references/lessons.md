# Confirmed Project Lessons

## Use the Yikai virtual-environment interpreter

- Trigger: Any Python, pytest, Streamlit, CLI, syntax-check, or project script
  command in this repository.
- Failure signature: A sandbox command reports `Unable to create process using`
  and names a missing or inaccessible base interpreter, or a guessed Python
  runtime lacks project packages such as pandas, tabulate, or Streamlit.
- Confirmed cause: The project packages and IDE runtime are exposed through the
  repository virtual environment. Its launcher depends on the base interpreter
  at `C:\Users\steve\AppData\Local\Programs\Python\Python312\python.exe`.
  That executable exists, but the default sandbox can deny access to it even
  though the same virtual environment works in the IDE and outside the sandbox.
- Prevention: Use this interpreter first and do not guess another path:
  `C:\Users\steve\OneDrive\Python Project\Yikai Code\venv\Scripts\python.exe`.
  In PowerShell, invoke it with the call operator:
  `& '.\venv\Scripts\python.exe' <arguments>`. For Codex tool calls, run this
  exact interpreter with the approved sandbox-escalation rule on the first
  attempt; do not spend an initial attempt running it inside the default
  sandbox.
- Recovery: If escalated execution also fails, confirm both the virtual-
  environment launcher and base executable exist before diagnosing the
  environment. Do not declare the environment broken and do not switch to an
  AppData or bundled Python merely because a default-sandbox launch failed. Use
  the Codex bundled Python only for an explicitly isolated, standard-library-
  only check and report that limitation.
- Verification: With sandbox escalation, run
  `& '.\venv\Scripts\python.exe' --version`, then import the project dependency
  or module needed by the task. For module-path ambiguity, print
  `module.__file__`.
- Last confirmed: 2026-08-16

## Restart stale Streamlit after helper-module changes

- Trigger: A Streamlit-visible change is present on disk but the live UI still
  shows the old layout or behavior, especially after editing files under
  `utils/`.
- Failure signature: Source and a fresh Python process contain the new function,
  while `http://localhost:8501` still renders the previous tabs or output.
- Confirmed cause: An existing Streamlit process may keep imported helper-module
  code in memory and may not hot-reload that dependency. Multiple old Streamlit
  process pairs can also exist for the same application.
- Prevention: After a Streamlit helper change, verify both the imported module
  path and the live UI. Do not assume hot reload occurred.
- Recovery: Identify the process listening on port 8501 and confirm its command
  targets this repository's `portfolio_analysis_streamlit.py`. Stop only the
  matching Yikai Streamlit process tree, then restart with the project virtual
  environment. Avoid launching a second server onto the occupied port.
- Verification: Load a representative current or historical PnL result in the
  browser, inspect the requested tab/table, and confirm the relevant raw console
  output when applicable.
- Last confirmed: 2026-08-08

## Validate through the real consumer

- Trigger: Shared helper, report generator, serialized historical data, or UI
  rendering changes.
- Failure signature: Unit tests or source inspection pass, but the user-facing
  workflow does not show the change.
- Confirmed cause: The tested helper may be correct while the live caller uses a
  stale process, a different branch, a different module path, or a separate data
  path.
- Prevention: Trace the actual caller and use the project entry point after the
  focused unit test.
- Recovery: Print loaded module paths, inspect the active branch and entry point,
  then run a minimal end-to-end check with representative local data.
- Verification: Confirm the requested console/UI behavior, not only function
  existence or successful compilation.
- Last confirmed: 2026-08-08

## Protected project-agent files need explicit write access

- Trigger: Creating or updating files below `.agents/`.
- Failure signature: Skill initialization or file creation returns Windows
  `Access is denied` although the project root is writable.
- Confirmed cause: The repository agent-instruction directory can have stricter
  sandbox write permissions than ordinary source files.
- Prevention: Use the standard skill-creator workflow and expect a narrowly
  scoped escalation for `.agents` writes.
- Recovery: Retry only the required `.agents` creation or validation command with
  explicit sandbox escalation. Do not broaden permissions to unrelated paths.
- Verification: Read the resulting files and run the skill validator.
- Last confirmed: 2026-08-08
