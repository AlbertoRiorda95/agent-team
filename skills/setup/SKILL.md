---
name: setup
description: Install the agent-team template into this repository for the harnesses, CI, tracker, roles and features the project uses (Claude Code, OpenCode, Codex), configure it (stack, commands, architecture), then run the first design studio. First time only; on a project that already has the template it stops and points to upgrade.
argument-hint: "(no arguments)"
disable-model-invocation: true
---

Install and configure the agent-team template in the current repository. Talk to
the user in their language; files stay in English.

`${CLAUDE_PLUGIN_ROOT}` is the plugin folder in Claude Code. In Codex or
OpenCode, which load these skills from `~/.agents/skills/`, use the folder where
the agent-team repository is cloned (`$AGENT_TEAM_HOME`) instead.

## 1. Check that this is a first install

- If `.agent-team/manifest.json` exists, the template is already installed: stop.
  Tell the user to use `/agent-team:upgrade` for a newer template version, and
  `/agent-team:design-studio`, `/agent-team:create-issues` or
  `/agent-team:split-issue` for the day-to-day work. Do nothing else.
- If `AGENTS.md`, `CLAUDE.md`, `.claude/agents/` or `SETUP.md` already exist
  without the manifest, the project was set up by hand or from an older copy of
  the template. Say so, and recommend `/agent-team:upgrade` instead: it compares
  file by file and never overwrites. Continue here only if the user insists.
- The folder must be a Git repository with no uncommitted changes (`git status
  --porcelain` empty). If it is not a repository, offer `git init`. If there are
  changes, ask the user to commit or stash them first. Then create the branch
  `chore/agent-team-setup`.

## 2. Choose the profile

Only the files of the profile are installed, so ask first (one round, with the
defaults proposed): blocks F and F2 of `${CLAUDE_PLUGIN_ROOT}/template/SETUP.md`
(scenario, issue tracker, harnesses and role runners, CI platform, roles,
features). Write the answers to a file outside the repository, for example
`${TMPDIR:-/tmp}/agent-team-profile.json`, in the format of block F2. Show the
profile in one line and ask for the user's yes.

## 3. Copy the template

1. Show what would happen:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/template_sync.py" install --template "${CLAUDE_PLUGIN_ROOT}/template" --project . --profile <profile file> --dry-run`
2. On the user's yes, run the same command without `--dry-run`. It writes the
   profile to `.agent-team/config.json`, adds the missing files of the profile,
   never overwrites an existing one, and writes `.agent-team/manifest.json` with a copy of each template file under
   `.agent-team/base/` (that is what makes later upgrades safe).
3. Existing files that differ (for example a `.gitignore` or a CI workflow the
   project already had) are listed and left alone. For each one, show the user
   the differences, propose a merge that keeps what the project has and adds
   what the template needs, apply it on their yes, then mark it merged:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/template_sync.py" record --template "${CLAUDE_PLUGIN_ROOT}/template" --project . --paths <file> ...`

## 4. Configure

Follow `SETUP.md`, now in the project root, from start to end: it interviews
the user (stack, commands, folders per role, scenario, models, skills),
shows every change before making it, runs the checks, and then runs the design studio for the project
design and, in an empty repository, the foundations spec.

- When `SETUP.md` asks for a design studio session, follow the procedure of
  the `design-studio` skill of this plugin.
- When it gets to the issues (remote and custom scenarios), follow the
  `create-issues` skill: dry run first, create only on the user's yes.
- Blocks F and F2 are already answered: do not ask them again. Its prune step
  should find nothing to remove; if the user changes the profile during the
  interview, update `.agent-team/config.json` and run
  `python3 scripts/agent-team.py prune` (to add things back, `/agent-team:upgrade`).

## 5. Finish

1. Run the checks again: `bash -n` on the changed `.sh` files, `python3 -m
   py_compile` on the `.py` files, `actionlint` on `.github/workflows/` if it is
   installed.
2. Commit everything on `chore/agent-team-setup`, including `.agent-team/`,
   with a message that lists what was configured.
3. Offer to push and open a pull request. Then give the user the open items
   from `SETUP.md` (secrets, labels, branch protection, required checks) as a
   short checklist.
