# 9. Reference

<!-- nav -->
[← 8. Change and upgrade](08-change-and-upgrade.md) · [Manual index](README.md)
<!-- /nav -->

## Skills

| Plugin skill | Template skill | What it does |
|---|---|---|
| `setup` | | installs and configures the template; first time only; `--to-issues` also creates the issues |
| `design-studio` | `/design-studio` | design session for the project, a feature or a whole milestone (`--milestone M0`), writes the specs; `--to-issues` goes on to the issues and the split |
| `create-issues` | | milestones and issues from the roadmap and the ready specs; turns "Design:" issues into features and tasks |
| `split-issue` | | one or several issues (or a milestone) into one task per role, after your approval of each |
| `dispatch` | | starts the ready tasks with the project's starter |
| `upgrade` | | new plugin version or new profile, keeping your changes |
| `next` | | where the project stands and the command to run next; reads only |
| | `/handoff` | a short note so a fresh session continues the work |
| | `clean-architecture` | layers for a backend with real business rules, preloaded by backend; removed by `setup` when the stack does not fit |
| | `/local-ci` | runs the CI checks on your computer and fixes the failures; for convenience or instead of a missing CI |
| | `/document` | has the `writer` agent write or update the software documentation in `docs/software/` |
| | `design-system` | the project's tokens and visual rules, preloaded by designer and frontend |

Claude can propose `next`, `design-studio`, `create-issues`, `split-issue` and
`dispatch` by itself; each shows its plan and asks before changing anything.
`setup` and `upgrade` run only when you type them.

**Plugin skills** come with the plugin (or the clone of the repository, for
Codex and OpenCode) and work in every project: in Claude Code they are
`/agent-team:<name>`; in Codex and OpenCode ask for them by name. **Template
skills** are copied into each project (`.claude/skills/`, `.agents/skills/`),
so they work for anyone who opens the project, with or without the plugin.
`design-studio` is both: the two run the same procedure,
`docs/roles/design-studio.md`; use the plugin's when you have it, since only
it has `--to-issues`.

## Scripts

| Command | What it does |
|---|---|
| `python3 scripts/agent-team.py profile` | the profile, and what is outside it |
| `python3 scripts/agent-team.py prune [--dry-run]` | removes files and sections outside the profile |
| `python3 scripts/tracker.py check \| config \| list \| show N` | the tracker: connection, settings, open issues, one issue |
| `python3 scripts/create-issues.py [--dry-run] [--team] [--migrate]` | milestones and issues; a "Design:" issue whose spec is ready becomes the task (one row) or the feature with the tasks as sub-issues; `--migrate` moves old "M0 · ..." parent issues to milestones |
| `python3 scripts/split-issue.py check \| propose \| create` | the split of one issue: validate a plan, post it, create it; `"depends_on": ["12:api"]` waits for a task of issue 12's plan, which must be created first |
| `python3 scripts/dispatch.py [--apply] [--per-role N] [--max N] [--milestone M1 \| --all]` | the ready tasks, checked against their spec row on the main branch; with `--apply` rewrites the changed ones and starts them |
| `scripts/git-hooks/spec-sync.sh` | feature `spec-sync`, local: Git hook (`post-merge`, `post-commit`) that runs create-issues after a spec change on the main branch |
| `./scripts/create-labels.sh` | GitHub labels |
| `./scripts/install-skills.sh`, `./scripts/check-skills.sh` | recommended skills for your stack, and a check that the agents find them |

## Files the agents read by situation

| File | When |
|---|---|
| `docs/agents/dependencies.md` | before adding a dependency or writing something generic |
| `docs/general/libraries.md` | the team's libraries: what they do, how to get them |
| `docs/agents/merge-requests.md` | opening or updating a merge request |
| `docs/agents/ci.md` | a check fails, or tests, UI, workflows or CI change |

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
| `GITLAB_ACCESS_TOKEN` | GitLab variable | splits; `spec-sync`; Codex and OpenCode merge requests |
| `JIRA_EMAIL` + `JIRA_API_TOKEN` or `JIRA_PAT`, `LINEAR_API_KEY`, `REDMINE_API_KEY` | GitHub secrets, GitLab variables | `spec-sync` and dispatch in CI with those trackers |
| `REGISTRY_TOKEN` | GitHub secret, GitLab masked variable | read access to the team's registry, when the job token is not enough (`ci/registry.sh`) |
| `REGISTRY_PUBLISH_TOKEN` | secret of the `release` environment (GitHub), protected variable of `release` (GitLab); on your computer, exported only for the command | publishing this project's package on a `v*` tag (`ci/registry.sh publish`) |
| `DEPENDABOT_REGISTRY_TOKEN` | Dependabot secret | Dependabot updates of the team's packages |
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

## What a run costs

Agent team adds no fees: you pay the model provider (an API key, billed per
token) or use your subscription's quota, plus CI minutes for runs in CI. A
run's cost depends on the model, the size of the task and of the code it
reads, so the template bounds each run instead:

| Run | Limit |
|---|---|
| a task, Claude Code on GitHub | 40 turns, 60 minutes |
| a team task, GitHub | 100 turns, 120 minutes |
| a task, Claude Code on GitLab | 30 turns |
| an `@claude` mention, an `ai-review` review | 15 turns each |
| Codex or OpenCode jobs | 60 minutes |

A turn is one model response, with its tool calls. Every run compacts its
context at 200,000 tokens. To see what runs actually cost, look at your
provider's usage page after a few tasks; with the custom orchestrator, the
Claude Agent SDK reports the cost of each run, and LiteLLM the spend per
role. Start with low dispatch limits (one task per role, three in total) and
raise them once you know your numbers.

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

For people who change the manual itself, in the plugin's repository; nothing
to do in your projects. The manual is written in Markdown, one file per chapter in `docs/manual/`.
`docs/manual.html` is generated from those files and never edited by hand:

```bash
pip install markdown==3.11.2
python3 scripts/build_manual.py           # regenerate docs/manual.html
python3 scripts/build_manual.py --check   # fails if the HTML is not built from the current Markdown
```

The HTML records a hash of the Markdown it was built from; `--check` compares
it with the files, and the repository's CI runs it on every pull request. To
check before every commit: `git config core.hooksPath .githooks`.

---

<!-- nav -->
[← 8. Change and upgrade](08-change-and-upgrade.md) · [Manual index](README.md)
<!-- /nav -->
