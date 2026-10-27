---
name: handoff
description: Write a short handoff note so a fresh session can continue this work with a small context, then tell the user to start a fresh session. Use when the conversation has grown long, before switching phase (design to implementation, one task to the next), or before stopping.
---

Write a handoff note for the work in this conversation, so that a new session
can continue it with a small context instead of this whole conversation.
If the user named the next session's focus, write the note for it.

1. Save it to `.handoff/<yyyy-mm-dd-hhmm>-<short-slug>.md` (the folder is
   git-ignored). Title line: `# Handoff: <what the work is>`.
2. Keep it short, at most about 60 lines, with these sections:
   - **Goal**: what the work is for, and what the next session should do.
   - **State**: done, in progress, not started; branch, pull request, issue
     numbers.
   - **Decisions**: the ones taken in this conversation and not yet recorded
     elsewhere, one line each with the reason.
   - **Open points**: questions waiting for the user, known problems, failing
     checks.
   - **Next steps**: in order, each one checkable.
   - **Where to look**: the files that matter, the commands to run the tests,
     how to verify the result.
   - **Skills and roles**: which skills or agents the next session should use.
3. Point, do not copy: specs, issues, pull requests, commits and docs are
   referenced by path or number, never pasted. The note holds only what exists
   nowhere else.
4. No secrets, tokens or personal data in the note.
5. Tell the user to start a new session (`/new`). In Codex the SessionStart hook
   points the new session to the note; elsewhere, or on another machine, the
   user starts it with "continue from .handoff/<file>".

Adapted from the `handoff` skill of mattpocock/skills (MIT).
