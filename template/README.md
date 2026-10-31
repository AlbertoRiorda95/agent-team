# Template: a team of AI coding agents

Starter repository for a team of development agents: designer, frontend,
backend and devops for everyday work, optimizer, security and writer (the documentation) on request, for Claude Code,
OpenCode and Codex. It is installed and kept up to date by the agent-team plugin,
whose user manual explains every scenario. It holds the team's configuration, not the application code.

## What's inside

```
SETUP.md                       instructions for the agent session that configures the template
AGENTS.md                      project rules for every harness
CLAUDE.md                      imports AGENTS.md + Claude Code-only notes
docs/roles/*.md                role prompts, written once
docs/security/                 security assessments (ignored by Git)
docs/design/                   project design (project.md) and one spec per feature, with templates
docs/roles/design-studio.md    the interactive design session (/design-studio)
docs/design-decisions.md       shared project decisions
docs/agents/                   rules by situation, pointed to by AGENTS.md (read only when they apply)
docs/api/                      API contract (openapi.yaml), owned by backend
docs/alignment/                one entry per change that other roles rely on
.claude/agents/*.md            the agents: model, effort, tools, skills
.claude/settings.json          denied permissions and hooks for every agent
scripts/hooks/*.sh             infra command blocker, test gate, lint, security scope, alignment reminder
docs/roles/security-scope.txt         hosts the security agent may test (local, staging)
.claude/skills/design-system/  project skill with tokens and visual rules
.opencode/agents/*.md          OpenCode: the six roles with permissions
opencode.json                  OpenCode: permissions; LiteLLM provider
.codex/                        Codex: config.toml, agents/*.toml (the roles), hooks.json, rules/
.agents/skills/                the project skills for Codex (and OpenCode without Claude Code)
.agent-team/config.json        the profile: harnesses, CI, tracker, roles, features (scripts/agent-team.py)
.github/workflows/             ci.yml (build, test, licenses, vulnerabilities); agent workflows
ci/                            CI security steps shared by GitHub and GitLab: syft, grype, trivy, semgrep
playwright.config.ts.example   UI tests: viewports, report, screenshots (rename to turn on the ui job)
e2e/ui.spec.ts.example         UI checks per screen: scroll, axe, focus, touch targets, screenshot
.github/CODEOWNERS             mandatory review on critical paths
.gitlab-ci.yml.example         GitLab pipeline: includes .gitlab/ci/ci.yml and .gitlab/ci/agents.yml
infra/litellm/                 LiteLLM gateway with Postgres and Caddy; local variant and key-spend.sh
scripts/                       skill installation and check, labels, issues from the specs (create-issues.py), issue split (split-issue.py), ready tasks (dispatch.py),
                               tracker check (tracker.py); agentteam/: the tracker API and its adapters
```

## First run

```bash
cp -r agent-team-template my-project && cd my-project
git init
claude                         # or codex, or opencode; then: "Read SETUP.md and set up this project"
```

The agent interviews you (project name, stack, commands, folders, scenario,
profile, models, skills), removes what the profile does not use, shows the plan of changes, edits the files and runs the checks.
`SETUP.md` lists every customization point; you can also follow it by hand.
With your confirmation it also installs the skills you chose
(`scripts/install-skills.sh`), checks them (`scripts/check-skills.sh`) and
commits them separately. Without network, or if you said no, run them later:

```bash
./scripts/install-skills.sh    # recommended skills
./scripts/check-skills.sh      # every skill named in the agents is installed
claude                         # ask for the list of agents to check
```

## What to customize

| File | What to change | Required |
|---|---|---|
| `AGENTS.md` | project name, stack, build and test commands, each role's folders | yes |
| `docs/roles/*.md` | boundary folders, commands, stack-specific rules | yes |
| `.claude/skills/design-system/SKILL.md` | tokens, components and rules of your design system | yes |
| `scripts/hooks/gate-test.sh` | test command | yes |
| `scripts/hooks/lint-frontend.sh` | file extensions and linter | yes |
| `scripts/install-skills.sh` | remove the skills that don't fit your stack | yes |
| `.claude/agents/*.md` | `skills:` field matching the installed skills; `model` and `effort` if you like | if you change stack |
| `.github/CODEOWNERS` | your username and the real critical paths | yes, for the remote scenario |
| `.claude/settings.json` | extra commands to deny, secret paths | if needed |
| `.github/workflows/*.yml`, `.gitlab-ci.yml.example` | `--allowedTools`: your stack's build and test commands | for the remote scenario |
| `docs/roles/security-scope.txt` | your staging host, if the security agent should test it | if you use security on staging |
| `.github/workflows/ci.yml`, `.gitlab/ci/ci.yml` | toolchain, install, lint, build and test commands, lockfile for the cache | yes |
| `ci/scanners.env` | tool versions, vulnerability threshold, license policy | if the defaults don't fit |
| `.github/workflows/agents.yml` | OpenCode action version, secrets and models | with OpenCode in CI |
| `opencode.json`, `.opencode/agents/*.md` | LiteLLM address, command permissions | with OpenCode |
| `infra/litellm/*` | models, domain, image version, `.env` file | with LiteLLM only |

`settings.json` and `opencode.json` don't allow comments: the spots to review are listed in this table.

## Profile: only what the project uses

The template supports Claude Code, OpenCode and Codex, GitHub and GitLab, six
issue trackers and optional features. A project keeps only its own part:
`.agent-team/config.json` lists harnesses, CI, tracker, roles and features, and
`python3 scripts/agent-team.py prune` removes the rest, files and sections
(SETUP.md does it during setup). Every agent then reads only instructions for
tools the project has.

To change later (another tracker, Codex next to or instead of Claude Code, a
role back): edit the profile and run the template upgrade
(`/agent-team:upgrade` with the plugin, otherwise the plugin's
`scripts/template_sync.py apply`). It adds what the new profile includes,
removes the template files it no longer includes if you never changed them,
and merges sections back into your files, keeping your edits.

- **Local:** the tool(s) you use, no tracker or `local`, the project CI.
- **Remote repository:** Claude Code: install the app with `/install-github-app`, add `ANTHROPIC_API_KEY` (or `CLAUDE_CODE_OAUTH_TOKEN`, switching the workflows to `claude_code_oauth_token`). Codex: `OPENAI_API_KEY` and, to have its PRs checked by CI, `AGENT_PR_TOKEN`. OpenCode: the provider secrets and `OPENCODE_MODEL`. With several tools, the `AGENT_RUNNERS` repository variable (for example `{"agent:frontend":"opencode","agent:optimizer":"codex"}`). Then `./scripts/create-labels.sh` and branch protection.
- **Custom orchestrator:** the tracker of its intake and a `start_command` (`docs/general/trackers.md`); `infra/litellm/` next to it if it routes models through LiteLLM.

## Notes

- The agents of each harness (`.claude/agents/`, `.opencode/agents/`, `.codex/agents/`) point to the prompt in `docs/roles/`: one definition per role. It costs one file read when each agent starts.
- optimizer, security and writer never run as routine steps: ask for them explicitly ("use optimizer on…", "run a security assessment", "document the application" or `/document`, or the `agent:optimizer` / `agent:security` / `agent:writer` label). A security assessment costs a few dollars on Opus, so run it once the app is complete or before a release.
<!-- agent-team:if issues -->
- Issues from the roadmap (remote and custom scenarios): `python3 scripts/create-issues.py --dry-run`, then without `--dry-run`, creates one native milestone per roadmap milestone (M0, M1, … on GitHub and GitLab) and, in it, the task issues of every ready spec and a "Design: <feature>" issue for every feature without a spec. No labels: start a task by adding `agent:<role>` to it. It skips existing titles and milestones, so run it again after every design studio session. Repositories set up with the old layout (one "M0 · …" parent issue with the tasks as sub-issues) move to milestones with `--migrate`. Needs the remote and an authenticated `gh` or `glab`, or another tracker (`docs/general/trackers.md`).
<!-- agent-team:end -->
<!-- agent-team:if split and harness_claude -->
- Splitting an issue (remote scenario): add `agent:split` to an issue (GitLab: run the pipeline with `SPLIT_ISSUE`). Claude proposes one task issue per role in a comment and creates nothing; reply `@claude ok` (GitLab: `SPLIT_CONFIRM=ok`) and `scripts/split-issue.py` creates exactly that plan as sub-issues in the parent's milestone, without labels. `@claude <changes>` asks for a new proposal. See AGENTS.md > Splitting issues.
<!-- agent-team:end -->
<!-- agent-team:if issues -->
- Issue trackers: the issue scripts work with GitHub, GitLab, local Markdown files (`docs/tasks/`), Jira, Linear and Redmine through one interface (`scripts/agentteam/`). How a task starts (the *starter*) is separate: a label, a GitLab pipeline, a command of yours such as an orchestrator, or a printed instruction. Configure both in `.agent-team/config.json` and check with `python3 scripts/tracker.py check`. See `docs/general/trackers.md`.
<!-- agent-team:end -->
<!-- agent-team:if dispatch -->
- Starting tasks: `python3 scripts/dispatch.py` shows which task issues are ready (no open dependency, a free slot for the role) and `--apply` starts them by adding their `agent:<role>` label: one per role and three in total by default. Optional `.github/workflows/dispatch.yml` does it every time an issue closes (needs `AGENT_AUTODISPATCH` and `AGENT_DISPATCH_TOKEN`). The `hold` label keeps a task out.
<!-- agent-team:end -->
<!-- agent-team:if harness_claude -->
- Context: `.claude/settings.json` compacts sessions at 200K tokens (`autoCompactWindow`) instead of near the 1M window, and the CI jobs do the same. `/handoff` writes a short note in `.handoff/` so a fresh session continues the work after `/clear`.
<!-- agent-team:end -->
- Foundations: in a new repository SETUP.md also writes `docs/design/foundations.md`, the spec of a walking skeleton (structure, contract served, database, tests, green CI). Implement it as the first task, before any feature.
- Design first: SETUP.md does not finish until `docs/design/project.md` exists and is ready. New features start with `/design-studio <feature>` (Claude Code or OpenCode, locally or in a Claude Code cloud session); implementation tasks then point to a spec marked `ready: yes`, and the issue template has a field for it.
- Alignment: when an agent changes something other roles rely on (API contract, data model, shared components, routes, env vars), it writes an entry in `docs/alignment/` and flags the MR. Locally the lead then runs designer and the affected roles automatically; in CI the MR gets the `alignment-needed` label and you create the follow-up tasks.
- On GitHub, enable branch protection on `main` with "Require branches to be up to date before merging": a PR built on an old contract then fails before the merge, not after. The Claude action does not rebase; use the "Update branch" button.
<!-- agent-team:if ci_github -->
- Workflow lint (GitHub): `workflow-lint.yml` runs actionlint on every PR, in its own file, because a mistake in `ci.yml` makes GitHub reject the whole file and no check appears. Make it a required check with the others.
<!-- agent-team:end -->
- CI: `ci.yml` (GitHub) and `.gitlab/ci/ci.yml` (GitLab) build, type-check and test every PR/MR, run static analysis (semgrep: on a PR only the findings it introduces fail it), generate the SBOM and the license report (saved as artifacts), apply the license policy and scan for vulnerabilities, secrets and misconfigurations. The security steps live in `ci/scan.sh`, the same on both platforms; versions and policies in `ci/scanners.env`.
<!-- agent-team:if ci_github and harness_claude -->
- AI review on request: `claude-review.yml` runs only when you add the `ai-review` label to a PR (created by `scripts/create-labels.sh`). It posts inline comments and changes nothing; to review again after new commits, remove the label and add it again. It costs tokens (or subscription quota) on every run, so use it on the PRs that deserve it.
<!-- agent-team:end -->
- Workflow safety: actions are pinned to a commit (the comment shows the version) and `.github/dependabot.yml` proposes updates weekly. The agent jobs run only on issues opened by the owner, a member or a collaborator, and read the issue with `gh issue view` as a task description, not as instructions.
- The infra command blocker (`scripts/hooks/block-infra-commands.sh`) is active for every agent: through `.claude/settings.json` in Claude Code, `.codex/hooks.json` and `.codex/rules/` in Codex; OpenCode uses the `permission` rules of `opencode.json` and of each agent.
- Make the scripts executable if the permissions got lost: `chmod +x scripts/hooks/*.sh scripts/*.sh infra/litellm/*.sh`.
- No secrets in the repository: keys go into the platform's secrets or into LiteLLM's `.env` file, which Git ignores.
