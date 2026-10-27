# 9. Reference

## Skills

| Plugin skill | Template skill | What it does |
|---|---|---|
| `setup` | | installs and configures the template; first time only |
| `design-studio` | `/design-studio` | design session for the project or a feature, writes the spec |
| `create-issues` | | milestones and issues from the roadmap and the ready specs |
| `split-issue` | | one issue into one task per role, after your approval |
| `dispatch` | | starts the ready tasks with the project's starter |
| `upgrade` | | new plugin version or new profile, keeping your changes |
| `next` | | where the project stands and the command to run next; reads only |
| | `/handoff` | a short note so a fresh session continues the work |
| | `design-system` | the project's tokens and visual rules, preloaded by designer and frontend |

Claude can propose `next`, `design-studio`, `create-issues`, `split-issue` and
`dispatch` by itself; each shows its plan and asks before changing anything.
`setup` and `upgrade` run only when you type them.

In Claude Code the plugin skills are `/agent-team:<name>`; in Codex and
OpenCode ask for them by name. Template skills live in the project
(`.claude/skills/`, `.agents/skills/`).

## Scripts

| Command | What it does |
|---|---|
| `python3 scripts/agent-team.py profile` | the profile, and what is outside it |
| `python3 scripts/agent-team.py prune [--dry-run]` | removes files and sections outside the profile |
| `python3 scripts/tracker.py check \| config \| list \| show N` | the tracker: connection, settings, open issues, one issue |
| `python3 scripts/create-issues.py [--dry-run] [--team] [--migrate]` | milestones and issues; `--migrate` moves old "M0 · ..." parent issues to milestones |
| `python3 scripts/split-issue.py check \| propose \| create` | the split: validate a plan, post it, create it |
| `python3 scripts/dispatch.py [--apply] [--per-role N] [--max N] [--milestone M1 \| --all]` | the ready tasks; starts them with `--apply` |
| `./scripts/create-labels.sh` | GitHub labels |
| `./scripts/install-skills.sh`, `./scripts/check-skills.sh` | recommended skills for your stack, and a check that the agents find them |

## Configuration

`.agent-team/config.json`, every key optional:

| Key | Meaning |
|---|---|
| `harnesses`, `runners`, `ci`, `roles`, `features` | the profile ([3. Set up a project](03-set-up-a-project.md#the-profile)) |
| `tracker` | `auto` (GitHub or GitLab from the remote, `local` without one), `github`, `gitlab`, `local`, `jira`, `linear`, `redmine`, `none` |
| `starter`, `start_command` | how a task starts (below) |
| `local` | `{"dir": "docs/tasks"}` |
| `jira` | `{"url", "project", "issue_type", "subtask_type"}` |
| `linear` | `{"team", "project"}`: milestones need a project |
| `redmine` | `{"url", "project", "started_status", "hold_status"}` |

Environment variables `AGENT_TEAM_TRACKER`, `AGENT_TEAM_STARTER` and
`AGENT_TEAM_START_COMMAND` override the file. Secrets only in the environment:
`JIRA_EMAIL` + `JIRA_API_TOKEN` or `JIRA_PAT`, `LINEAR_API_KEY`, `REDMINE_API_KEY`.

## Starters

| Starter | What "start" does | Default for |
|---|---|---|
| `label` | adds `agent:<role>`; on GitHub that starts the agent workflow | GitHub |
| `gitlab-pipeline` | adds `agent:<role>` and runs the agent pipeline | GitLab |
| `command` | marks the task, runs `start_command` with `{number} {id} {ref} {role} {title} {url} {tracker} {harness}` | any tracker, when `start_command` is set |
| `print` | marks the task and prints how to start it in a session | the other trackers |

## Labels

| Label | Meaning |
|---|---|
| `agent:<role>` | the task runs on that role; on GitHub adding it starts the agent |
| `agent:team` | GitHub: one coordinator runs the roles of the `Roles:` line (GitLab: `AI_FLOW_ROLES`) |
| `agent:split` | GitHub: Claude proposes a split in a comment (GitLab: `SPLIT_ISSUE`) |
| `hold` | dispatch never starts this task |
| `alignment-needed` | the merge request changes something other roles rely on |
| `ai-review` | two reviews of the pull request, rules and spec |

## CI secrets and variables

| Name | Where | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` | GitHub secret, GitLab variable | Claude Code jobs |
| `OPENAI_API_KEY` | secret / variable | Codex jobs |
| `CODEX_MODEL` | GitHub variable | Codex model (empty: Codex's default) |
| `AGENT_PR_TOKEN` | GitHub secret | Codex pull requests that start the CI |
| `OPENCODE_MODEL`, provider keys | variable, secrets | OpenCode jobs |
| `AGENT_RUNNERS`, `AGENT_DEFAULT_RUNNER` | GitHub variables | which tool runs which role |
| `AGENT_AUTODISPATCH`, `AGENT_DISPATCH_TOKEN` | GitHub variable, secret | dispatch at every merge |
| `AGENT_DISPATCH_PER_ROLE`, `AGENT_DISPATCH_MAX` | GitHub variables | its limits (1 and 3) |
| `GITLAB_ACCESS_TOKEN` | GitLab variable | splits; Codex and OpenCode merge requests |
| `AI_FLOW_*`, `TASK_ID`, `SPLIT_*` | GitLab pipeline variables | starting a job ([6. Scenario: remote](06-scenario-remote.md#gitlab)) |

## Where the tools find things

| | Claude Code | Codex | OpenCode |
|---|---|---|---|
| Project rules | `CLAUDE.md` → `AGENTS.md` | `AGENTS.md` | `AGENTS.md` |
| Roles | `.claude/agents/*.md` | `.codex/agents/*.toml` | `.opencode/agents/*.md` |
| Skills | `.claude/skills/` | `.agents/skills/` | `.claude/skills/` or `.agents/skills/` |
| Forbidden commands | `.claude/settings.json` | `.codex/rules/agent-team.rules` | `permission` in `opencode.json` and agents |
| Hooks | `.claude/settings.json` → `scripts/hooks/` | `.codex/hooks.json` → `scripts/hooks/` | none |
| Settings | `.claude/settings.json` | `.codex/config.toml` | `opencode.json` |

## Token costs

What every agent reads on every turn costs on every request: `AGENTS.md`
(about 1,200 tokens after setup), `CLAUDE.md`, the descriptions of the agents
and skills of the tool in use, and the tools of active MCP servers. Role
prompts, specs and `docs/agents/` cost only when an agent opens them. Files
of other tools, trackers and workflows cost nothing unless an agent searches
or opens them: the profile removes them anyway, so no agent stumbles on
instructions for tools you do not have.

To keep costs down: one task per session, handoff notes instead of long
sessions, MCP servers only on the agents that need them, and few skills per
role.

## This manual

The manual is written in Markdown, one file per chapter in `docs/manual/`.
`docs/manual.html` is generated from those files and never edited by hand:

```bash
pip install markdown==3.11.2
python3 scripts/build_manual.py           # regenerate docs/manual.html
python3 scripts/build_manual.py --check   # fails if the HTML is not built from the current Markdown
```

The HTML records a hash of the Markdown it was built from; `--check` compares
it with the files, and the repository's CI runs it on every pull request. To
check before every commit: `git config core.hooksPath .githooks`.
