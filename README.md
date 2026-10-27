# Agent team

**Run your software project as the lead of a development team whose
developers are AI agents.** You decide what to build in a design session,
approve the plan, choose what starts, and merge. The team (designer,
frontend, backend, devops; optimizer and security when you ask) asks the
questions, writes the specs, turns them into issues, implements each task on
its own branch and opens merge requests that explain themselves.

It works with **Claude Code, Codex and OpenCode**, and in three scenarios:

| Scenario | The agents run | You need to be there | Good for |
|---|---|---|---|
| **Local** | in your session, on your computer | yes | starting in minutes, exploring, design work |
| **Remote repository** | in GitHub Actions or GitLab CI, started from issues | no: you come back to merge requests | a backlog, parallel tasks, a full trail |
| **Custom orchestrator** | where your orchestrator runs them, from Jira, Linear, Redmine or your queue | no | your tracker, your infrastructure, your priorities |

Design, issues, splits, dispatch and upgrades work the same in all three.

## Get started

```bash
claude plugin marketplace add <owner>/claude-agent-team
claude plugin install agent-team@agent-team
```

Then, in your repository: `/agent-team:setup`. With Codex or OpenCode, see
[Install](docs/manual/02-install.md#in-codex-or-opencode).

## Manual

The user manual is in [`docs/manual/`](docs/manual/README.md), and as a single
page in [`docs/manual.html`](docs/manual.html):

1. [What Agent team is](docs/manual/01-what-it-is.md)
2. [Install](docs/manual/02-install.md)
3. [Set up a project](docs/manual/03-set-up-a-project.md)
4. [Run the project](docs/manual/04-run-the-project.md)
5. [Scenario: local](docs/manual/05-scenario-local.md)
6. [Scenario: remote repository](docs/manual/06-scenario-remote.md)
7. [Scenario: custom orchestrator](docs/manual/07-scenario-custom.md)
8. [Change and upgrade](docs/manual/08-change-and-upgrade.md)
9. [Reference](docs/manual/09-reference.md)

## Commands

| Command | What it does |
|---|---|
| `/agent-team:setup` | installs the template for your profile (tools, CI, tracker, roles, features) and configures it |
| `/agent-team:design-studio <feature>` | a design session with the designer: questions in rounds, a ready spec with its task breakdown |
| `/agent-team:create-issues` | milestones and issues from the roadmap and the ready specs, after a dry run |
| `/agent-team:split-issue <n>` | one issue into one task per role, created only after your yes |
| `/agent-team:dispatch` | starts the tasks whose dependencies are merged |
| `/agent-team:upgrade` | a new plugin version, or a new profile, merged with your changes |

## Repository layout

```
.claude-plugin/     plugin manifest and marketplace (plugin "agent-team")
skills/             the six skills above (also usable from Codex and OpenCode)
scripts/            template_sync.py (install and upgrade), build_manual.py (the HTML manual)
template/           the project template the plugin installs
docs/manual/        the user manual, one Markdown file per chapter
docs/manual.html    the same manual as one page, generated
tests/              template install and upgrade, profiles, trackers
```

## Develop

```bash
claude plugin validate . --strict          # manifest, marketplace, skills
bash tests/test_template_sync.sh           # install and upgrade scenarios
python3 tests/test_profiles.py             # every sample profile renders, loads and lints; switching profiles
python3 tests/test_trackers.py             # issue scripts on the six trackers (fakes)
python3 scripts/build_manual.py            # after editing docs/manual/*.md
git config core.hooksPath .githooks        # refuse commits with a stale docs/manual.html
```

The `Validate` workflow runs these checks on every pull request, plus
`actionlint` on the template's workflows and `build_manual.py --check`. For
every release, bump `version` in `.claude-plugin/plugin.json` and add a
`CHANGELOG.md` entry with its upgrade notes: projects stay on the version they
installed until they upgrade.

## Credits and license

MIT, see `LICENSE`. Some rules in the template adapt ideas from
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT): see `NOTICE.md`.
