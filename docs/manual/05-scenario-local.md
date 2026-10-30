# 5. Scenario: local

The team runs on your computer, inside your session. You talk to the main
session (the agent you started), which hands each task to the role agent and
reports back. Everything in
[4. Run the project](04-run-the-project.md) applies; this chapter adds how to
work with each tool.

## Why use it

| Good for | Watch out |
|---|---|
| Starting in minutes: no secrets, no workflows, no server | You need to be there: when you close the session, the work stops |
| A tight feedback loop: you see each step and correct it at once | One machine: tasks run one after another or a few at a time, on your laptop's resources |
| Exploring, prototypes, small features, design work | Less trail: decisions live in commits and specs, not in issue threads, unless you also use a tracker |
| Alignment handled automatically: the main session runs designer and the affected roles right away | Your subscription or API budget pays for every turn of every agent |
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
the same. With GitHub or GitLab issues but no `ci-agents` feature, dispatch
does not add labels that would start CI jobs: it prints what to run, as for
the other trackers. Keep `ci` for the project's own CI: it checks your merge
requests even when nobody runs agents there.

## What a task produces

Each task is done on its own branch (`feat/<task>-<slug>`), with small commits.
At the end the agent runs the tests and, if the repository has a remote,
pushes the branch and opens a merge request, which the project's CI checks;
your tool asks before running those commands unless you allowed them. Without
a remote, the branch stays on your computer: review it and merge it yourself.
Agents never push to `main` and never merge. With a tracker, the merge
request closes the issue on GitHub and GitLab; on the other trackers, close it
yourself after the merge (for local files, `state: "done"`).

## Where the CI runs

The project's CI (`ci.yml` on GitHub, `.gitlab/ci/ci.yml` on GitLab) is run by
the platform that hosts the repository, not by your computer. Working locally
does not change that: the agents run on your machine, but the checks need the
repository to be on GitHub or GitLab. The template takes it for granted that
the code is hosted there, even if all the development happens locally:

- **With a remote.** The agent pushes the branch and opens the merge request;
  the CI runs on it and you see the result in the merge request or with `gh pr
  checks`, `gh run list` (GitHub) or `glab ci status` (GitLab). You can
  therefore check that a commit passes before you merge. An agent running
  locally waits for the checks and fixes what fails
  (rule in `docs/agents/ci.md`). Turn on branch
  protection so that a red CI blocks the merge
  ([4. Review and merge](04-run-the-project.md#review-and-merge)). A private
  repository is enough: nobody else needs to see the code.
- **Without a remote.** Nothing runs in CI: there is no platform to run it. The
  same steps are scripts you can run yourself, and the `/local-ci` skill runs
  them all and fixes what fails (below).
- **No CI at all.** With `"ci": "none"` in the profile the CI files are not
  installed. Agents still follow TDD and the test gate; vulnerabilities and
  licenses are checked by nobody. Use it for throwaway experiments.

### Run the CI checks locally: `/local-ci`

The template skill `local-ci` runs on your computer the same checks as the CI:
build, type check, tests, UI tests (when `playwright.config.ts` exists),
static analysis, licenses, vulnerabilities and secrets. It reads the project's
CI file and `AGENTS.md > Commands` to know what to run, runs every check, fixes
the failures and runs the failed ones again (three rounds at most).

```text
> /local-ci                    all the checks
> /local-ci static             only one: build, test, ui, static, licenses, vulnerabilities
```

Use it for convenience, before you push, so the real CI does not come back
red; or as the **alternative to the CI** when the project has no real one
(no remote, or `"ci": "none"`). It fixes the cause, not the check: it never
weakens a test, edits `ci/scanners.env` or suppresses a finding; false
positives, licenses and secrets that must be rotated are reported to you. The
fixes stay in the working tree, uncommitted. It is not the real CI: a green run
on your computer proves nothing to anyone else, and the platform's CI stays
the one that gates the merge. The security steps need the network, to install
their tools and fetch the vulnerability data.

## With Claude Code

Start `claude` in the repository. The roles are subagents in `.claude/agents/`:

```text
> @backend implement task 2 of docs/design/login.md
> implement the login feature from docs/design/login.md   (the main session delegates by role)
> @devops add a staging deploy job                       (it writes the config, never applies it)
```

- Each agent preloads its skills and has its own context; the main session receives a
  summary, not the whole work.
- Hooks: commands that change real environments are blocked for everyone; a
  role agent cannot report its task as finished while the test suite fails
  (the test gate: it must fix them first); after each delegation the main
  session is reminded of open alignment entries; frontend files are linted
  when saved.
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
  rules in `AGENTS.md` that the main session follows, not checks.
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

A local session does not need issues: give the main session a spec and a
task number. With a tracker, ask it to pick work from it:

```text
> /agent-team:dispatch             the ready tasks; on your yes, marks them as started
  #14: start it yourself: in a session, delegate to @backend with "carry out #14"
> carry out #14                    the main session reads the issue and hands it to backend
```

Dispatch marks the task as started (`agent:backend`) and prints how to run
it; it runs nothing by itself. Run it in this session, or in a second terminal
to work on two tasks at once. You can also run the scripts yourself in a
shell: `python3 scripts/dispatch.py` shows the plan, `--apply` marks the tasks.

To have dispatch open the session for you, set a start command in
`.agent-team/config.json`, for example on Linux with GNOME:

```json
{"starter": "command",
 "start_command": "gnome-terminal -- claude \"carry out {id} following docs/roles/{role}.md\""}
```

The command runs without a shell, with `{id}`, `{role}` and the other values
of [9. Starters](09-reference.md#starters) filled in.

## Keep the issues in line with the specs

Dispatch already checks every task against its spec row before starting it
([4. When a spec changes](04-run-the-project.md#when-a-spec-changes-after-its-issues-exist)).
To update the issues as soon as a spec change lands, without running
create-issues yourself, add `spec-sync` to the profile and link its Git hook
once (check first that `.git/hooks/` has no `post-merge` or `post-commit` of
yours):

```bash
ln -s ../../scripts/git-hooks/spec-sync.sh .git/hooks/post-merge
ln -s ../../scripts/git-hooks/spec-sync.sh .git/hooks/post-commit
```

After a commit, merge or pull on the main branch that changed `docs/design/`,
it runs `scripts/create-issues.py`: new rows get issues, changed rows of tasks
not started rewrite them. A failure is printed and never blocks Git. The hook
sees only what happens in this clone: a merge done in a web interface counts
at your next `git pull`.

## The skills by example

A short example of each skill in a local project (profile with `"tracker":
"local"`, issues as files in `docs/tasks/`). Replies are in one line: the
agent asks numbered questions and you answer by number.

**setup** - once, in an empty or existing repository:

```text
> /agent-team:setup
  (it asks harnesses, tracker, roles, stack; "1 claude, 2 local, 3 all roles")
```

**next** - when you do not know what to do:

```text
> /agent-team:next
  Design: project ready, "login" ready, "orders" not. Issues: none yet.
  Next: /agent-team:create-issues
```

**design-studio** - before building a feature:

```text
> /agent-team:design-studio orders
  Round 1 - 1. Who filters the list? (recommended: the customer) ...
> 1 yes, 2 by date and status, 3: option B
```

**create-issues** - after a design session; it shows the plan first:

```text
> /agent-team:create-issues
  milestone create   M1 · Login, Orders
      rename  #9  Design: login (M1)  ->  Login (M1)
      create        Login · 1/2 · backend: Auth endpoint   (sub-issue of #9)
      create        Login · 2/2 · frontend: Login page   (depends on: task 1)   (sub-issue of #9)
> yes
```

**split-issue** - for an issue written by hand, in `docs/tasks/`:

```text
> /agent-team:split-issue 7
  1 backend: date filter in the API   2 frontend: date picker (after 1)
> ok 7
```

**dispatch** - to see what is ready; in a local project it marks the tasks
and prints what to run:

```text
> /agent-team:dispatch
  Would start (2): #1 backend, #3 devops. Waits: #2 (needs #1)
> yes
  #1: start it yourself: in a session, delegate to @backend with "carry out #1"
  #3: start it yourself: in a session, delegate to @devops with "carry out #3"
> carry out #1
```

**The two flows in one go** - with `--to-issues` each flow runs to the issues
and stops before dispatch ([4. The workflow](04-run-the-project.md#the-workflow)).
Without a remote there is no merge request: the specs are committed on a
`design/...` branch that you merge yourself. Without a remote, dispatch reads
the specs from the commit you are on, so run it from your main branch after
the merge.

```text
> /agent-team:setup --to-issues
  ... configuration, project design, foundations spec ...
  create-issues: M0 foundations tasks #1-#3, M1 Design: #4 login, #5 orders. Create?
> yes
  Next: /agent-team:dispatch (foundations), then /agent-team:design-studio --milestone M1 --to-issues

> /agent-team:design-studio --milestone M1 --to-issues
  ... one round of questions for login and orders ...
> ok login; ok orders
  create-issues: #4 becomes "Login (M1)" with 2 sub-issues, #5 becomes the orders task. Create?
> yes
  Split: none needed. Start with /agent-team:dispatch.
```

**upgrade** - after a new plugin version, or to add a tool:

```text
> /agent-team:upgrade
  update 3 files, merge 1, add 2. Work on a branch, one commit.
> yes
```

## From your phone

To drive the session from the Claude app, start it with Remote Control:

```bash
claude --remote-control "my-project"     # or type /remote-control in a session
```

Then open the session in the app and ask "what's next?" (Claude runs `next`) or
type `/agent-team:dispatch`. The terminal must stay running: the work happens
on your computer, the app is only a window on it.
