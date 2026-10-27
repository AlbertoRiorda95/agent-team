# 2. Install

Agent team ships as one repository, `agent-team`. It is a Claude Code
plugin, and its skills also work in Codex and OpenCode.

## In Claude Code

```bash
claude plugin marketplace add AlbertoRiorda95/agent-team
claude plugin install agent-team@agent-team
```

Inside a session the same steps are under `/plugin`. The commands then appear
as `/agent-team:<skill>`:

| Command | Use it to |
|---|---|
| `/agent-team:setup` | install the template in a repository and configure it |
| `/agent-team:design-studio <feature>` | design the project or a feature with the designer |
| `/agent-team:create-issues` | turn the roadmap and the ready specs into milestones and issues |
| `/agent-team:split-issue <n>` | split one issue into one task per role |
| `/agent-team:dispatch` | start the tasks that are ready |
| `/agent-team:upgrade` | bring the project to a new plugin version or a new profile |
| `/agent-team:next` | see where the project stands and which command to run next (read-only) |

Claude can propose `next`, `design-studio`, `create-issues`, `split-issue` and
`dispatch` by itself when they fit; each shows its plan and asks before changing
anything. `setup` and `upgrade` run only when you type them, so they can also
be typed from the Claude app.

To try a local checkout without installing: `claude --plugin-dir ./agent-team`.

## In Codex or OpenCode

Both read skills from `~/.agents/skills/`. Clone the repository once and link
its skills there:

```bash
git clone https://github.com/AlbertoRiorda95/agent-team ~/agent-team
mkdir -p ~/.agents/skills
ln -s ~/agent-team/skills/* ~/.agents/skills/
echo 'export AGENT_TEAM_HOME=~/agent-team' >> ~/.bashrc   # or your shell's file
```

The skills use `AGENT_TEAM_HOME` where Claude Code would use the plugin
folder. Ask for them by name ("use the setup skill", "run the design-studio
skill for login") or, in Codex, with `$setup`, `$design-studio`.

## Without the plugin

Copy `template/` into a new repository and ask your tool to follow
`SETUP.md`:

```bash
cp -r agent-team/template my-project && cd my-project && git init
claude        # or codex, or opencode
# then: "Read SETUP.md and set up this project"
```

The setup works the same. What you miss: the commands above, and upgrades
that merge new template versions with your changes. To get them later, run
the upgrade from a clone ([8. Change and upgrade](08-change-and-upgrade.md#a-project-set-up-by-hand)).

## Updating the plugin

```bash
claude plugin marketplace update agent-team
claude plugin update agent-team@agent-team
```

In Codex and OpenCode: `git pull` in the clone. Updating the plugin does not
touch your projects: run `/agent-team:upgrade` in each one when you want the
new template ([8. Change and upgrade](08-change-and-upgrade.md)).

## What each tool needs

| Tool | Install | Notes |
|---|---|---|
| Claude Code | `curl -fsSL https://claude.ai/install.sh \| bash` | API key or Claude subscription |
| Codex | `npm install -g @openai/codex` | trust the project once, so it reads `.codex/`; approve its hooks with `/hooks` |
| OpenCode | `curl -fsSL https://opencode.ai/install \| bash` or `npm install -g opencode-ai` | connect the providers you use with `/connect` |

Python 3.11 or newer and Git are needed by the scripts; `gh` or `glab` for
GitHub or GitLab issues.
