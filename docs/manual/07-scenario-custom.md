# 7. Scenario: custom orchestrator

Here the issues live in the tracker you already use, and the agents run where
you decide, started by something you control. Agent team gives you the
planning side (design, issues, split, dispatch) on any supported tracker, and
one hook for the execution side: the *starter command*. What runs the agents
is up to you; this chapter shows two ways.

Everything in [4. Run the project](04-run-the-project.md) applies.

## Why use it

| Good for | Watch out |
|---|---|
| Your tracker: Jira, Linear, Redmine, or GitHub/GitLab issues with your own runner | You build and run the execution side: a service, a server, its updates |
| Your infrastructure: the code never leaves your network, your runners, your credentials | Protections are yours too: tokens that cannot push to `main` or merge, no production credentials where agents run |
| Control: priorities, queues, retries, concurrency, cost per task, any mix of tools and models | More moving parts to watch than a CI job |
| A board people already use, with agents as one more kind of assignee | The CI workflows in the template are for GitHub and GitLab: on other platforms, keep your own CI |

Choose it when the first two scenarios are not enough for a concrete reason:
a company tracker, code that must stay on your machines, a queue with
priorities. Otherwise start [remote](06-scenario-remote.md) and move later.

## The connection points

**Planning, on your tracker.** Set it in the profile and check it:

```json
{
  "harnesses": ["claude", "opencode"],
  "ci": "none",
  "tracker": "jira",
  "jira": {"url": "https://example.atlassian.net", "project": "APP"},
  "starter": "command",
  "start_command": "python3 /opt/team/enqueue.py --issue {number} --role {role} --harness {harness} --url {url}"
}
```

```bash
python3 scripts/tracker.py check
```

| Concept | Jira | Linear | Redmine | Files (`local`) |
|---|---|---|---|---|
| Milestone | version (Fix Version) | project milestone | version | `docs/tasks/_milestones.json` |
| Sub-issue | sub-task | sub-issue | parent task | `parent` field |
| Dependency | "Blocks" link | "blocks" relation | "blocks" relation | text |
| Started | label `agent:<role>` | label | status (`started_status`) | label |

Create issues, split and dispatch work as in chapter 4. The split proposal is
approved in your session instead of with a comment.

**Execution, through the starter.** When dispatch starts a task, it marks it
as started and runs `start_command` with the issue's data: `{number}` (12,
APP-12), `{id}`, `{ref}`, `{role}`, `{title}`, `{url}`, `{tracker}` and
`{harness}` (the tool for that role: `runners`, otherwise the first of the
profile). The command is split into arguments before the values are filled
in and runs without a shell, so an issue title cannot inject commands. A
command that fails is reported for that task (which stays marked as started:
remove the label to retry) and dispatch exits with an error.

So your orchestrator needs one entry point that accepts a task, and a way to
tell the tracker when the work is done (a merge request linked to the issue,
or a status change). Two ways to build the rest follow.

## Option A: Multica, a board with agents as team members

[Multica](https://github.com/multica-ai/multica) is a self-hosted board where
agents appear as team members: you assign an issue to an agent as to a
colleague, it picks up the work, updates the status and reports blockers. A
daemon on a server of yours runs the installed tools (Claude Code, Codex,
OpenCode and others).

How it fits:

- One agent per role in Multica, each with its tool (runtime) and model.
  Point them to the role prompts: "follow docs/roles/<role>.md and AGENTS.md".
- Plan with Agent team (design studio, specs), then create and assign the
  tasks in Multica, by hand or from `start_command` through its API.
- A server with at least 4 vCPUs and 8 GB of RAM (builds and tests run
  there), the tools installed and logged in as the daemon's user, a Git token
  that can open merge requests but never push to `main` or merge, and no
  cluster, cloud or registry credentials on that machine.

Good when you want a visual board for agents running on different tools.
Multica is young and changes fast: check its README before installing.

## Option B: your own orchestrator

A small service that takes tasks from a queue and runs the right tool in a
clean checkout. The starter command only enqueues; a worker does the rest:

```text
dispatch.py --apply  →  start_command (enqueue)  →  queue  →  worker
                                                      worker: checkout, run the tool, push, open the MR,
                                                              update the tracker with the result and the cost
```

The worker runs each tool non-interactively, in the repository, with the
same prompt the CI jobs use:

| Tool | Command |
|---|---|
| Claude Code | `claude -p "<task>" --permission-mode acceptEdits --max-turns 40` |
| Codex | `codex exec --sandbox workspace-write --output-last-message summary.md "<task>"` |
| OpenCode | `opencode run --agent <role> --model <provider/model> "<task>"` |

For more control, use the tools' libraries instead of their command lines:
the Claude Agent SDK (`@anthropic-ai/claude-agent-sdk` or `claude-agent-sdk`
for Python) streams each step and reports the cost of the run; load the
project settings (`settingSources: ["project"]`) so it reads `CLAUDE.md` and
`.claude/`.

Rules for the worker:

- one container or VM per task, with write access to that repository only;
- a Git token that can push branches and open merge requests, never push to
  `main` or merge;
- no production, cluster or registry credentials;
- record the cost and the outcome on the task, so you notice a role that
  burns budget.

Good when you need priorities, retries, your own infrastructure or a
dashboard of your own. It is your code to maintain: start with the simplest
queue that works.

## LiteLLM: one gateway for many providers

With OpenCode on several providers, the `litellm` feature adds
`infra/litellm/`: a LiteLLM gateway (with Postgres and Caddy) that gives each
role a virtual key with its own budget, and one place to see costs per role
and model. Run it next to your orchestrator, listening only on the local
interface, or on a small server for CI. `infra/litellm/key-spend.sh` shows
what each key spent; `docker-compose.local.yml` runs it on your computer for
a trial.
