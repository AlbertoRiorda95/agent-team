#!/usr/bin/env python3
"""The guardrails inside real sessions of the tools, with a scripted model
(tests/mockllm.py) in place of the provider: no API key, no cost. The model
asks for a tool call; the test checks what the tool did with it: the hook or
the permission blocked it (and the command never ran), or it ran.

Claude Code: the hooks of .claude/settings.json and of the role agents, the
Read deny rules, the role subagents with their model. Codex: the role agents
load and the rules block. OpenCode: the role agents load and their
permissions block.

Each tool is skipped when its CLI is missing (validate.yml installs them).
Run: python3 tests/test_sessions.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE = os.path.join(ROOT, "template")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(TEMPLATE, "scripts"))
import mockllm  # noqa: E402
from agentteam import profile  # noqa: E402

SECRET = "npm_SECRETtoken0123456789"
# a command only the hook blocks (no permission rule names it), and a fake npm that leaves a trace
PUBLISH = "npm --registry https://r.example publish"
FAKE = """#!/bin/sh
echo "$(basename "$0") $*" >> "{trace}"
"""


def tool(env_name, *names):
    for n in (os.environ.get(env_name), *names):
        if n and shutil.which(n):
            return shutil.which(n)
    return None


def put(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    if mode:
        os.chmod(path, mode)


def bash(command):
    return {"tool": "Bash", "input": {"command": command, "description": "step"}}


class Session:
    """A project rendered for the harness, a HOME of its own, fake npm/kubectl/curl, the scripted model."""

    def __init__(self, test, cfg):
        self.server = mockllm.Server()
        test.addCleanup(self.server.close)
        self.tmp = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = os.path.join(self.tmp, "proj")
        self.home = os.path.join(self.tmp, "home")
        self.trace = os.path.join(self.tmp, "trace")
        profile.render_tree(TEMPLATE, self.dir, cfg)
        os.makedirs(os.path.join(self.dir, "src"))
        put(os.path.join(self.home, ".npmrc"), f"//registry.npmjs.org/:_authToken={SECRET}\n")
        fake_bin = os.path.join(self.tmp, "bin")
        for name in ("npm", "kubectl", "curl", "terraform"):
            put(os.path.join(fake_bin, name), FAKE.format(trace=self.trace), 0o755)
        # a repository with an origin, as a real project (the security-review skill reads origin/HEAD)
        origin = os.path.join(self.tmp, "origin.git")
        git_env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                       GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull)
        for cmd in (["git", "init", "-q", "--bare", "-b", "main", origin], ["git", "init", "-q", "-b", "main"],
                    ["git", "add", "-A"], ["git", "commit", "-q", "-m", "project"],
                    ["git", "remote", "add", "origin", origin], ["git", "push", "-q", "origin", "main"],
                    ["git", "remote", "set-head", "origin", "main"]):
            subprocess.run(cmd, cwd=self.dir, check=True, env=git_env, capture_output=True)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("CLAUDE", "ANTHROPIC", "OPENAI", "CODEX", "OPENCODE"))}
        self.env.update(HOME=self.home, PATH=fake_bin + os.pathsep + os.environ["PATH"],
                        XDG_CONFIG_HOME=os.path.join(self.home, ".config"),
                        XDG_DATA_HOME=os.path.join(self.home, ".local/share"),
                        XDG_CACHE_HOME=os.path.join(self.home, ".cache"),
                        XDG_STATE_HOME=os.path.join(self.home, ".local/state"))

    def path(self, *p):
        return os.path.join(self.dir, *p)

    def ran(self):
        if not os.path.exists(self.trace):
            return []
        with open(self.trace) as f:
            return f.read().splitlines()

    def run(self, cmd, timeout=240):
        r = subprocess.run(cmd, cwd=self.dir, env=self.env, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
        return r


CLAUDE = tool("CLAUDE_BIN", "claude")


@unittest.skipUnless(CLAUDE, "claude not installed")
class Claude(unittest.TestCase):
    def session(self, *steps, setup=None, args=()):
        s = Session(self, {"harnesses": ["claude"], "ci": "github", "tracker": "github", "features": []})
        if setup:
            setup(s)
        s.env.update(ANTHROPIC_BASE_URL=s.server.url, ANTHROPIC_API_KEY="sk-ant-mock",
                     CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1", DISABLE_AUTOUPDATER="1")
        r = s.run([CLAUDE, "-p", mockllm.script(*steps), "--output-format", "json",
                   "--permission-mode", "bypassPermissions", *args])
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        s.result = json.loads(r.stdout)
        s.results = s.server.tool_results()
        return s

    def agent(self, role, *steps):
        return {"tool": "Agent", "input": {"subagent_type": role, "description": f"{role} task",
                                           "prompt": mockllm.script(*steps), "run_in_background": False}}

    def test_hook_blocks_and_the_command_never_runs(self):
        s = self.session(bash(PUBLISH), bash("echo allowed"))
        self.assertIn("Blocked", s.results[0])
        self.assertEqual(s.results[1].strip(), "allowed")
        self.assertEqual(s.ran(), [])

    def test_hook_still_blocks_after_cd(self):
        s = self.session(bash("cd src && pwd"), bash(PUBLISH), bash("kubectl -n prod apply -f x.yaml"))
        self.assertTrue(s.results[0].strip().endswith("/src"), s.results[0])
        self.assertIn("Blocked", s.results[1])
        self.assertIn("Blocked", s.results[2])
        self.assertEqual(s.ran(), [])

    def test_credentials_cannot_be_read(self):
        s = self.session(bash("cat ~/.npmrc"), {"tool": "Read", "input": {"file_path": "~/.npmrc"}},
                         bash("grep -r token $HOME/.npmrc"))
        self.assertEqual(len(s.results), 3)
        for r in s.results:
            self.assertNotIn(SECRET, r)

    def test_role_subagent_loads_with_its_model_and_hooks(self):
        s = self.session(self.agent("backend", bash("kubectl -n prod apply -f x.yaml"), bash("echo from-backend")))
        sub = [q for q in s.server.requests if "docs/roles/backend.md" in json.dumps(q["body"].get("system", ""))]
        self.assertTrue(sub, "the backend agent's prompt never reached the model")
        self.assertIn("opus", sub[0]["body"]["model"])                       # model: opus in the frontmatter
        self.assertTrue(any("Blocked" in r for r in s.results), s.results)
        self.assertTrue(any("from-backend" in r for r in s.results), s.results)
        self.assertEqual(s.ran(), [])

    def test_every_role_starts_with_its_model(self):
        roles = ("designer", "frontend", "backend", "optimizer", "devops", "security", "writer")
        s = self.session(*[self.agent(r, bash(f"echo role-{r}")) for r in roles])
        for r in roles:
            with self.subTest(role=r):
                with open(s.path(".claude", "agents", f"{r}.md")) as f:
                    front = f.read()
                model = re.search(r"^model: (\S+)", front, re.M).group(1)
                tools = {t.strip() for t in re.search(r"^tools: (.*)$", front, re.M).group(1).split(",")}
                sub = [q for q in s.server.requests if f"docs/roles/{r}.md" in json.dumps(q["body"].get("system", ""))]
                self.assertTrue(sub, f"{r}: never reached the model")
                self.assertIn(model, sub[0]["body"]["model"])
                # the tools: line, no more; Claude Code gives Write and Edit together (role-hooks.sh checks both)
                given = {t["name"] for t in sub[0]["body"]["tools"]}
                self.assertEqual("Bash" in given, "Bash" in tools)
                self.assertEqual(bool(given & {"Write", "Edit"}), bool(tools & {"Write", "Edit"}))
                ran = any(f"role-{r}" in x for x in s.results)
                self.assertEqual(ran, "Bash" in tools, f"{r}: Bash in tools is {'Bash' in tools}")

    def test_writer_writes_only_documentation(self):
        s = self.session(self.agent("writer",
                                    {"tool": "Write", "input": {"file_path": "src/app.ts", "content": "x"}},
                                    {"tool": "Write", "input": {"file_path": "docs/software/guide.md", "content": "# G\n"}}))
        self.assertFalse(os.path.exists(s.path("src", "app.ts")), s.results)
        self.assertTrue(os.path.exists(s.path("docs", "software", "guide.md")), s.results)

    def test_security_stays_in_scope(self):
        s = self.session(self.agent("security", bash("curl -s https://evil.example.com/"), bash("curl -s evil.example.com"),
                                    bash("curl -s http://localhost:3000/")))
        self.assertEqual(s.ran(), ["curl -s http://localhost:3000/"])

    def test_role_hooks_in_ci(self):
        """The CI runs a role as the session's agent (claude -p --agent <role>), in a folder nobody trusted."""
        s = self.session({"tool": "Write", "input": {"file_path": "src/app.ts", "content": "x"}},
                         {"tool": "Write", "input": {"file_path": "docs/software/guide.md", "content": "# G\n"}},
                         args=("--agent", "writer"))
        self.assertFalse(os.path.exists(s.path("src", "app.ts")), s.results)
        self.assertTrue(os.path.exists(s.path("docs", "software", "guide.md")), s.results)
        s = self.session(bash("curl -s https://evil.example.com/"), bash("curl -s http://localhost:3000/"),
                         args=("--agent", "security"))
        self.assertEqual(s.ran(), ["curl -s http://localhost:3000/"])

    def test_lead_is_not_limited_by_the_roles(self):
        s = self.session({"tool": "Write", "input": {"file_path": "src/app.ts", "content": "x"}},
                         bash("curl -s https://example.org/"))
        self.assertTrue(os.path.exists(s.path("src", "app.ts")), s.results)
        self.assertEqual(s.ran(), ["curl -s https://example.org/"])

    def test_alignment_reminder_after_a_delegation(self):
        def entry(s):
            put(s.path("docs", "alignment", "2026-01-01-api.md"), "---\nstatus: open\n---\n# API change\n")
        s = self.session(self.agent("backend", bash("echo x")), setup=entry)
        self.assertIn("docs/alignment/2026-01-01-api.md", json.dumps([q["body"] for q in s.server.requests]))

    def test_handoff_pointer_at_startup(self):
        def note(s):
            put(s.path(".handoff", "2026-01-01.md"), "# Login feature, halfway\n")
        s = self.session(setup=note)
        self.assertIn("Login feature, halfway", json.dumps(s.server.requests[0]["body"]))



ORCHESTRATOR = """import json, os, subprocess, sys
number, role, harness, title = sys.argv[1:5]
with open(os.environ["QUEUE"], "a") as f:
    f.write(json.dumps({"number": number, "role": role, "harness": harness, "title": title}) + "\\n")
# the worker: the role's agent, headless, on the task (chapter 7, option B)
steps = [{"tool": "Bash", "input": {"command": f"mkdir -p work && echo {role} > work/task-{number}.txt",
                                    "description": "work"}},
         {"tool": "Bash", "input": {"command": "npm --registry https://r.example publish", "description": "publish"}}]
prompt = f"Carry out issue {number} following docs/roles/{role}.md. MOCK: " + json.dumps(steps) + " END"
subprocess.run(["claude", "-p", prompt, "--agent", role, "--permission-mode", "acceptEdits",
                "--allowedTools", "Bash", "--max-turns", "10"], check=True, stdout=subprocess.DEVNULL)
"""
PROJECT_SPEC = "---\nready: yes\n---\n# Project\n\n## Roadmap\n| Milestone | Features |\n|---|---|\n| M0 | Shell |\n"
SHELL_SPEC = """---
ready: yes
milestone: M0
features: Shell
---
# Shell

## Task breakdown
| # | Role | Task | Depends on | Issue |
|---|---|---|---|---|
| 1 | backend | Menu endpoint; touch PWNED | - | - |
| 2 | frontend | Menu | 1 | - |
| 3 | devops | CI pipeline | - | - |
"""


@unittest.skipUnless(CLAUDE, "claude not installed")
class CustomScenario(unittest.TestCase):
    """Chapter 7: create-issues on the tracker, dispatch --apply, start_command to an orchestrator,
    whose worker runs the role's agent headless (claude -p --agent) against the scripted model."""

    def test_dispatch_to_an_orchestrator(self):
        s = Session(self, {"harnesses": ["claude"], "ci": "none", "tracker": "local", "features": ["dispatch"]})
        queue = os.path.join(s.tmp, "queue.jsonl")
        put(os.path.join(s.tmp, "orchestrator.py"), ORCHESTRATOR)
        put(s.path("docs", "design", "project.md"), PROJECT_SPEC)
        put(s.path("docs", "design", "shell.md"), SHELL_SPEC)
        put(s.path(".agent-team", "config.json"), json.dumps({
            "tracker": "local", "starter": "command", "harnesses": ["claude"],
            "start_command": f"python3 {os.path.join(s.tmp, 'orchestrator.py')} {{number}} {{role}} {{harness}} {{title}}"}))
        put(s.path(".gitignore"), "docs/tasks/\nwork/\n")
        git = lambda *a: subprocess.run(["git", *a], cwd=s.dir, check=True, capture_output=True, env=dict(  # noqa: E731
            s.env, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))
        git("add", "-A")
        git("commit", "-q", "-m", "design")
        git("push", "-q", "origin", "main")
        s.env.update(QUEUE=queue, ANTHROPIC_BASE_URL=s.server.url, ANTHROPIC_API_KEY="sk-ant-mock",
                     CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1", DISABLE_AUTOUPDATER="1")
        r = s.run(["python3", "scripts/create-issues.py"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = s.run(["python3", "scripts/dispatch.py", "--apply"], timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        with open(queue) as f:
            started = [json.loads(line) for line in f]
        self.assertEqual(sorted(t["role"] for t in started), ["backend", "devops"])   # frontend waits for task 1
        self.assertTrue(all(t["harness"] == "claude" for t in started))
        self.assertTrue(any(t["title"].endswith("Menu endpoint; touch PWNED") for t in started))  # one argument, no shell
        self.assertFalse(os.path.exists(s.path("PWNED")))
        for t in started:                                     # each worker did its task as its role
            with open(s.path("work", f"task-{t['number']}.txt")) as f:
                self.assertEqual(f.read().strip(), t["role"])
        self.assertEqual(s.ran(), [])                         # and could not publish
        r = s.run(["python3", "scripts/dispatch.py", "--apply"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(queue) as f:
            self.assertEqual(len(f.readlines()), 2)           # nothing started twice

CODEX = tool("CODEX_BIN", "codex")
ROLES = ("backend", "designer", "devops", "frontend", "optimizer", "security", "writer")


@unittest.skipUnless(CODEX, "codex not installed")
class Codex(unittest.TestCase):
    """codex exec against the scripted model, the project trusted (Codex reads .codex/ only then)."""

    def session(self, *steps):
        s = Session(self, {"harnesses": ["codex"], "ci": "github", "tracker": "github", "features": []})
        codex_home = os.path.join(s.home, ".codex")
        put(os.path.join(codex_home, "config.toml"),
            f'model = "mock-model"\nmodel_provider = "mock"\n\n[model_providers.mock]\nname = "mock"\n'
            f'base_url = "{s.server.url}/v1"\nwire_api = "responses"\nenv_key = "MOCK_API_KEY"\n\n'
            f'[projects."{s.dir}"]\ntrust_level = "trusted"\n')
        s.env.update(CODEX_HOME=codex_home, MOCK_API_KEY="mock")
        r = s.run([CODEX, "exec", "--json", mockllm.script(*steps)])
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        s.results = s.server.tool_results()
        return s

    def test_roles_load_with_their_effort(self):
        s = self.session()
        tools = json.dumps(s.server.requests[0]["body"]["tools"])
        for role in ROLES:
            with open(os.path.join(TEMPLATE, ".codex", "agents", f"{role}.toml")) as f:
                effort = re.search(r'^model_reasoning_effort = "(\w+)"', f.read(), re.M).group(1)
            with self.subTest(role=role):
                self.assertRegex(tools, rf"{role}: {{\\n.*?reasoning effort is set to `{effort}`")

    def test_rules_block_in_a_session(self):
        cmd = lambda c: {"tool": "exec_command", "input": {"cmd": c}}   # noqa: E731
        blocked = ["npm publish", "git push --tags", "terraform apply", "./gradlew publish", "cd lib && mvn -B deploy",
                   "pip config list"]
        s = self.session(*map(cmd, blocked + ["echo allowed"]))
        for c, r in zip(blocked, s.results):
            with self.subTest(cmd=c):
                self.assertIn("rejected", r)
        self.assertIn("allowed", s.results[len(blocked)])
        self.assertEqual(s.ran(), [])


OPENCODE = tool("OPENCODE_BIN", "opencode")


@unittest.skipUnless(OPENCODE, "opencode not installed")
class OpenCode(unittest.TestCase):
    """opencode run --agent <role> against the scripted model. A denied call ends the run: one call per session."""

    def session(self, role, step, answered=True):
        s = Session(self, {"harnesses": ["opencode"], "ci": "github", "tracker": "github", "features": []})
        cfg = os.path.join(s.tmp, "mock-provider.json")
        put(cfg, json.dumps({"provider": {"mock": {
            "npm": "@ai-sdk/openai-compatible", "name": "Mock",
            "options": {"baseURL": s.server.url + "/v1", "apiKey": "mock"},
            "models": {"mock-model": {"name": "Mock"}}}}}))
        s.env.update(OPENCODE_CONFIG=cfg, PWD=s.dir)          # opencode takes its folder from PWD
        r = s.run([OPENCODE, "run", "--agent", role, "-m", "mock/mock-model", mockllm.script(step)])
        s.results = s.server.tool_results()
        s.output = r.stdout + r.stderr
        if answered:
            self.assertTrue(s.results, s.output[-2000:])
        return s

    def test_denied_commands_never_run(self):
        for role in ("backend", "devops", "writer"):
            for c in ("npm publish", "git push --tags", "terraform apply"):
                with self.subTest(role=role, command=c):
                    s = self.session(role, bash(c))
                    self.assertIn("prevents you from using this specific tool call", s.results[0])
                    self.assertEqual(s.ran(), [])

    def test_unlisted_commands_are_not_run_unattended(self):
        """"*": ask, and nobody answers in opencode run: a command outside the allow list does not run."""
        s = self.session("backend", bash("npm --registry https://r.example publish"), answered=False)
        self.assertIn("rejected permission", s.output)
        self.assertEqual(s.ran(), [])

    def test_allowed_command_runs(self):
        s = self.session("backend", bash("git status"))
        self.assertIn("On branch main", s.results[0])

    def test_writer_edits_only_documentation(self):
        s = self.session("writer", {"tool": "write", "input": {"filePath": "src/app.ts", "content": "x"}})
        self.assertFalse(os.path.exists(s.path("src", "app.ts")))
        s = self.session("writer", {"tool": "write", "input": {"filePath": "docs/software/guide.md", "content": "# G\n"}})
        self.assertTrue(os.path.exists(s.path("docs", "software", "guide.md")), s.results)

if __name__ == "__main__":
    unittest.main()
