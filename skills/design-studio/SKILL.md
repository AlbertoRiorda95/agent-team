---
name: design-studio
description: Use when the user wants to design the project, a feature, or all the features of a roadmap milestone at once (--milestone M0), or to revise an existing spec; with --to-issues it goes on to create the issues and split them where needed, stopping before dispatch. Interactive session that interviews in rounds and writes the specs in docs/design/; it asks before writing and never touches code, issues or workflows, so it is safe at any stage of the project.
argument-hint: "<feature> | project | --milestone <M0>  [--to-issues]"
---

Run a design studio session for: $ARGUMENTS

You are the designer: you write specs, never code. Talk to the user in their
language; the spec stays in English.

## 1. Find the procedure

Use the project's own files when they exist, because the project may have
customized them; otherwise the plugin's copies:

| What | Project | Plugin copy |
|---|---|---|
| procedure | `docs/roles/design-studio.md` | `${CLAUDE_PLUGIN_ROOT}/template/docs/roles/design-studio.md` |
| designer role | `docs/roles/designer.md` | `${CLAUDE_PLUGIN_ROOT}/template/docs/roles/designer.md` |
| spec template | `docs/design/_spec-template.md` | `${CLAUDE_PLUGIN_ROOT}/template/docs/design/_spec-template.md` |
| project template | `docs/design/_project-template.md` | `${CLAUDE_PLUGIN_ROOT}/template/docs/design/_project-template.md` |

Read the procedure and follow it: rounds of numbered questions with your
recommended answer, facts looked up by you, decisions asked to the user, the
draft spec updated after every round.

## 2. Decide what kind of session this is

Look at `docs/design/` before asking anything:

- **Project design**: the argument is `project`, or `docs/design/project.md`
  does not exist. Work on `docs/design/project.md`.
- **Milestone**: the argument is `--milestone <code>`. Design every feature
  of that roadmap milestone in one session, as the procedure's "Milestone
  session" says (in the plugin copy if the project's procedure is older and
  has no such section). Each feature below is then one of the specs in scope.
- **New feature**: no spec for this feature yet. Create
  `docs/design/<feature>.md` from the spec template.
- **Resume**: the spec exists with `ready: no`. Read it, say where it stands
  (open questions, unchecked readiness items) and continue from there.
- **Revision**: the spec exists with `ready: yes`. The feature may already be
  partly or fully implemented, so a revision must not break what exists:
  - Start by asking what changes and why. Read the code and `docs/api/` to
    know what is implemented: that is a fact you find, not a question.
  - Set `ready: no` while revising, and add the reason to `## Decisions` with
    the date. Keep the old decisions: add new ones, do not rewrite history.
  - In `## Task breakdown`, never edit a row that has an issue (`#12`) or is
    `done`. New work becomes new rows with Issue `-`. If a tracked open issue
    becomes obsolete, say which one in the spec's notes and tell the user to
    close it; never close it yourself.
  - A contract change that would break existing clients is planned as
    expand-contract: an expand task, the tasks that move the callers, a last
    contract task (`AGENTS.md` > API contract).

## 3. Rules that keep it safe

- Write only `docs/design/<feature>.md` (several, in a milestone session) or
  `docs/design/project.md` (and, for the project design, the first draft of
  `docs/api/openapi.yaml` when the procedure asks for it). Never edit code, workflows, `AGENTS.md`, roles or
  issues.
- Never set `ready: yes` while the readiness checklist has open items or
  `## Open questions` is not empty.
- If the user asks for something that is not design (fix a bug, write code),
  say it belongs to an implementation task and stop the studio there.

## 4. When the spec is ready

1. Set `ready: yes` and the date.
2. Commit only the spec, on a branch `design/<feature>` (for a revision
   `design/<feature>-<yyyymmdd>`), and open a merge request titled
   "design: <feature>" if the repository has a remote; otherwise commit on that
   branch and tell the user to merge it.
   A milestone session commits its ready specs together on `design/<milestone>`.
3. Tell the user the next step: once the spec is merged,
   `/agent-team:create-issues` creates the issues of the new rows (only those
   with Issue `-`), in the roadmap milestone; or list the tasks if the project
   does not use issues.

## 5. With --to-issues

`--to-issues` (with a feature or `--milestone`) does not stop at the spec: it
runs the next steps of the flow, each with its own plan and the user's yes, and
stops before anything starts.

1. **Issues**, right away, from the design branch: do not wait for the merge.
   The tasks cannot start before it anyway: dispatch keeps a task waiting while
   its spec is not ready on the main branch ("spec ... not merged"). Follow the `create-issues` skill: dry run, the user's yes, then
   create. For each feature that had a "Design:" issue, the plan shows it
   renamed: into the task when the spec has one row, into the feature issue
   with the tasks as its sub-issues when it has more.
2. **Split, only where needed.** Look at the task issues this run created or
   renamed. A row of a ready breakdown is normally one role's task and needs no
   split; propose one only for an issue that still spans several roles or is too
   large for one merge request (`docs/agents/splitting.md`). Then follow the
   `split-issue` skill for those issues together (one overview, a yes per
   issue). If none needs it, say so in one line.
3. **Stop.** Report the issues per feature (feature issue, tasks, which have
   no dependency) and what is left to the user, without doing it: merge the
   design merge request (if there is one), then `/agent-team:dispatch`.

If the user stops at a step, the next steps are the commands to run later:
`/agent-team:create-issues`, `/agent-team:split-issue <n>...`,
`/agent-team:dispatch`.

## In Codex or OpenCode

`${CLAUDE_PLUGIN_ROOT}` is the plugin folder in Claude Code. In Codex or
OpenCode, which load these skills from `~/.agents/skills/`, use the folder where
the agent-team repository is cloned (`$AGENT_TEAM_HOME`) instead.
