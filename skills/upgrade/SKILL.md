---
name: upgrade
description: Bring a project to the template version shipped with this plugin, or to a new profile (another tracker, Codex or OpenCode next to or instead of Claude Code, a role or feature back), file by file, keeping the project's own changes - safe updates where the project did not change a file, three-way merges where both changed, nothing deleted or overwritten silently. Also adopts projects set up by hand or from an older copy of the template.
argument-hint: "(no arguments)"
disable-model-invocation: true
---

Upgrade this project to the agent-team template in this plugin. Talk to the
user in their language.

Paths used below:
- script: `${CLAUDE_PLUGIN_ROOT}/scripts/template_sync.py`
- template: `${CLAUDE_PLUGIN_ROOT}/template`
- release notes: `${CLAUDE_PLUGIN_ROOT}/CHANGELOG.md`

`${CLAUDE_PLUGIN_ROOT}` is the plugin folder in Claude Code. In Codex or
OpenCode, which load these skills from `~/.agents/skills/`, use the folder where
the agent-team repository is cloned (`$AGENT_TEAM_HOME`) instead.

## 1. Prepare

- The working tree must be clean (`git status --porcelain` empty); otherwise
  ask the user to commit or stash first. Create the branch
  `chore/agent-team-upgrade-<plugin version>`. Every change will be reviewable
  with `git diff` before anything is committed.
- Run `python3 <script> status --template <template> --project .` and read
  `.agent-team/manifest.json` if it exists.
- Read the release notes for the versions newer than the project's
  (`plugin_version` in the manifest; all of them if there is no manifest),
  in particular the "Upgrade notes": steps that are not file changes
  (labels, secrets, required checks, migrations).

## 2. The profile

`.agent-team/config.json` says which harnesses, CI, tracker, roles and features
the project uses; the template is rendered for it, so the profile decides what
the upgrade adds and removes (`template/scripts/agentteam/profile.py`).

- If it has no `"harnesses"` key, the project predates profiles and would get
  every harness, CI and tracker of the template. Before anything else, propose a
  profile from what the project has (`.claude/`, `.opencode/`, `.codex/`,
  `.github/workflows/`, `.gitlab/`, the tracker settings, `docs/roles/`), in the
  format of block F2 of `<template>/SETUP.md`, and write it on the user's yes.
- If the user asked to change something (another tracker, Codex instead of or
  next to Claude Code, a role or a feature back or away), update the profile
  with them, then run `status` again.

## 3. Explain the plan

Group the status for the user, in this order:

| Kind | What happens |
|---|---|
| `add` | new template file: added |
| `update` | the project never changed it: replaced with the new version |
| `merge` | both changed: three-way merge that keeps the project's changes |
| `differs-no-base` | no record of the installed version (project set up by hand or before the plugin): you compare and merge by hand with the user |
| `removed-upstream` | gone from the template: kept; say what replaced it, the user decides |
| `removed-by-you` | the project deleted it: not added back |
| `prune` | outside the profile and never changed by the project: removed |
| `out-of-profile` | outside the profile but changed by the project: kept; ask the user whether to delete it |

Summarize, per file or group, what the template change is about (from the
release notes and the diff), not just the file names. Ask for the user's yes;
they can exclude files.

## 4. Apply

1. `python3 <script> apply --template <template> --project . --kinds add,update,merge,prune`
   (add `--paths ...` to limit it to the files the user accepted).
2. Conflicts are left between `<<<<<<< project` and `>>>>>>> template`
   markers. Resolve each one with the user: keep the project's intent, take the
   template's new content, never drop either side silently. Show the result.
3. For `differs-no-base` files, one at a time: show the differences between the
   project file and the template, explain which ones are the project's own
   customizations (stack, commands, folders, models, secrets) and which are
   template improvements, and propose a merged version that keeps the first and
   adds the second. Write it on the user's yes, then
   `python3 <script> record --template <template> --project . --paths <file>`.
4. Never delete a project file yourself (the script removes only unchanged
   `prune` files) and never touch the files the status reports as `owned`.
5. After a harness change, tell the user what that harness needs once: Codex
   reads `.codex/` only in a trusted project and asks to approve its hooks with
   `/hooks`; new CI secrets (`OPENAI_API_KEY`, provider keys) and variables
   (`AGENT_RUNNERS`) are listed in `.github/workflows/agents.yml`.

## 5. Check and finish

1. No conflict markers left: `git grep -n '^<<<<<<< project'` must be empty.
2. Checks: `bash -n` on changed `.sh` files, `python3 -m py_compile` on changed
   `.py` files, `actionlint` on `.github/workflows/` if installed, a YAML parse
   of changed `.yml` files.
3. Show `git diff --stat`, then commit on the branch, including `.agent-team/`.
4. Give the user the "Upgrade notes" that need their hands (labels, secrets,
   required checks, commands to run such as `create-issues.py --migrate`) as a
   checklist, and offer to push and open a pull request.
