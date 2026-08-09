---
name: project-operational-memory
description: Project-specific operational memory for every coding, debugging, testing, Python execution, Streamlit, CLI, data workflow, and environment task in the Yikai Code repository. Use before running commands or editing code to apply confirmed lessons from earlier failures, avoid repeating known mistakes, choose the verified interpreter and runtime path, and record newly confirmed project-specific failure patterns after the task.
---

# Yikai Project Operational Memory

Use confirmed project history to avoid rediscovery and repeated failed commands.

## Mandatory workflow

1. Scan the headings in `references/lessons.md` before the first command.
2. Read only entries whose `Trigger` matches the planned task. Always read the
   interpreter lesson for Python commands and the Streamlit lesson for UI work.
3. Use the documented prevention or recovery path before experimenting.
4. Do not repeat a command with the same known failure condition. Apply the
   recorded workaround or gather new evidence.
5. Verify user-visible behavior through the actual project entry point. Source
   inspection alone is insufficient.
6. When a new project-specific lesson is confirmed, propose the lesson and get
   user approval before modifying the existing lessons file.

## Recording a lesson

Append concise entries to `references/lessons.md` using this schema:

```markdown
## Short lesson name

- Trigger:
- Failure signature:
- Confirmed cause:
- Prevention:
- Recovery:
- Verification:
- Last confirmed: YYYY-MM-DD
```

Keep entries factual and reusable. Update an existing entry instead of adding a
near-duplicate. Never record credentials, API keys, account identifiers, or
private portfolio values.

## Decision rules

- Treat the project interpreter and entry points in the lessons file as the
  default until direct evidence shows they changed.
- Distinguish sandbox restrictions from a broken local environment.
- Prefer one verified command over trying several guessed runtimes.
- For UI work, verify the live server loaded the modified module and render the
  requested state with representative local data.
- Preserve user processes and files. Restart only the identified project process
  when restart is required, and never delete data as a workaround.