# 5. Scenario: local

The team runs on your computer, inside your session. You talk to a lead
session, which delegates to the role agents and reports back. Everything in
[4. Run the project](04-run-the-project.md) applies; this chapter adds how to
work with each tool.

## Why use it

| Good for | Watch out |
|---|---|
| Starting in minutes: no secrets, no workflows, no server | You need to be there: when you close the session, the work stops |
| A tight feedback loop: you see each step and correct it at once | One machine: tasks run one after another or a few at a time, on your laptop's resources |
| Exploring, prototypes, small features, design work | Less trail: decisions live in commits and specs, not in issue threads, unless you also use a tracker |
| Alignment handled automatically: the lead runs designer and the affected roles right away | Your subscription or API budget pays for every turn of every agent |
| Your own credentials and tools, no CI minutes | Long sessions grow expensive: use handoff notes |

Choose it to begin with, for one-person projects, and for the design work of
any project. Move to the [remote scenario](06-scenario-remote.md) when the
backlog grows and you want the team to work while you do something else.

## Profile

```json
{"harnesses": ["claude"], "ci": "github", "tracker": "none", "features": []}
```

Use `"tracker": "local"` to keep issues as Markdown files in `docs/tasks/`,
or your real tracker if the project has one: issues, splits and dispatch work
the same. Keep `ci` for the project's own CI: it checks your merge requests
even when nobody runs agents there.

## With Claude Code

Start `claude` in the repository. The roles are subagents in `.claude/agents/`:

```text
> @backend implement task 2 of docs/design/login.md
> implement the login feature from docs/design/login.md   (the lead delegates by role)
> @devops add a staging deploy job                       (it writes the config, never applies it)
```

- Each agent preloads its skills and has its own context; the lead receives a
  summary, not the whole work.
- Hooks: commands that change real environments are blocked for everyone; a
  task cannot be closed while the tests fail; after each delegation the lead
  is reminded of open alignment entries; frontend files are linted when saved.
- Denied commands (`git push --force`, push to `main`, merge, `terraform
  apply`...) are in `.claude/settings.json`.
- **Agent teams** (experimental in Claude Code): several agents work in
  parallel and message each other. Turn them on with
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` set to `"1"` in `.claude/settings.json`.
  Good for a feature where frontend and backend must agree as they go.

## With Codex

Start `codex` in the repository and trust it when asked: only then Codex
reads `.codex/`. Approve the project hooks once with `/hooks`.

```text
> have backend implement task 2 of docs/design/login.md
> spawn frontend and backend in parallel for docs/design/login.md, tasks 2 and 3
```

- The roles are custom agents in `.codex/agents/*.toml`, each with its
  reasoning effort; at most three run at once.
- Forbidden commands are in `.codex/rules/agent-team.rules`, and the same
  hook as Claude Code blocks commands on real environments.
- Codex has no per-agent hooks: the test gate and the alignment reminder are
  rules in `AGENTS.md` that the lead follows, not checks.
- Pin the model in `.codex/config.toml` if you do not want Codex's default.

## With OpenCode

Start `opencode` in the repository. The roles are agents in
`.opencode/agents/`, usable as subagents (`@backend ...`) or as the main agent
(switch with Tab).

- Permissions are rules in `opencode.json` and in each agent: commands on
  real environments and merges are denied, other shell commands ask first.
- OpenCode has no hooks in the template: its permission rules are the
  protection.
- With LiteLLM (feature `litellm`) OpenCode reaches any provider through one
  gateway with budgets per key ([7. Scenario: custom](07-scenario-custom.md#litellm-one-gateway-for-many-providers)).

## Several tools in one project

People in the same project can use different tools: list them all in
`harnesses`. They share `AGENTS.md`, the role prompts, the specs and the
skills; each tool reads its own folder. The design, the issues and the
handoff notes are the same for everybody.

## Issues in the local scenario

A local session does not need issues: give the lead a spec and a task number.
With a tracker, the lead can pick work from it:

```text
> python3 scripts/dispatch.py      shows the ready tasks
> implement issue #14              the lead reads it and delegates to its role
```

The default starter for trackers other than GitHub and GitLab prints the
command to start each task; with `"starter": "command"` it can open a new
terminal session for you instead ([9. Reference](09-reference.md#starters)).
