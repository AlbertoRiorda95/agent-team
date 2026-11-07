#!/usr/bin/env python3
"""The project's helper scripts in a rendered project, with Git and fake CLIs:
create-labels.sh (a fake gh records the labels), the spec-sync Git hook
(a merge on main that changes a spec creates the issues of the local
tracker), check-skills.sh and install-skills.sh (a fake npx records the
skills.sh calls), and the GitHub files the workflows do not cover
(dependabot.yml) against the schemas GitHub publishes.

Run: python3 tests/test_scripts.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE = os.path.join(ROOT, "template")
sys.path.insert(0, os.path.join(TEMPLATE, "scripts"))
from agentteam import profile  # noqa: E402

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull}
RECORDER = """#!/bin/sh
printf '%s\\n' "$*" >> "$RECORD"
"""
SPEC = """---
ready: yes
---
# Shell

## Task breakdown
| # | Role | Task | Depends on | Issue |
|---|---|---|---|---|
| 1 | backend | Menu endpoint | - | - |
| 2 | frontend | Menu | 1 | - |
"""


def put(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    if mode:
        os.chmod(path, mode)


class Project:
    """A project rendered from the template for a profile, a Git repository on main."""

    def __init__(self, test, cfg):
        self.dir = tempfile.mkdtemp()
        test.addCleanup(shutil.rmtree, self.dir, True)
        profile.render_tree(TEMPLATE, self.dir, cfg)
        self.bin = os.path.join(self.dir, ".fake-bin")
        self.record = os.path.join(self.dir, ".record")
        self.env = dict(os.environ, **GIT_ENV, RECORD=self.record, PATH=self.bin + os.pathsep + os.environ["PATH"])
        self.git("init", "-q", "-b", "main")

    def path(self, *p):
        return os.path.join(self.dir, *p)

    def fake(self, name):
        put(os.path.join(self.bin, name), RECORDER, 0o755)

    def calls(self):
        if not os.path.exists(self.record):
            return []
        with open(self.record) as f:
            return f.read().splitlines()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, env=getattr(self, "env", dict(os.environ, **GIT_ENV)),
                              check=True, capture_output=True, text=True)

    def run(self, *cmd):
        r = subprocess.run(list(cmd), cwd=self.dir, env=self.env, capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout + r.stderr


class CreateLabels(unittest.TestCase):
    def labels(self, cfg):
        p = Project(self, cfg)
        p.fake("gh")
        rc, out = p.run("bash", "scripts/create-labels.sh")
        self.assertEqual(rc, 0, out)
        for call in p.calls():
            self.assertTrue(call.startswith("label create ") and call.endswith(" --force"), call)
        return {c.split()[2] for c in p.calls()}

    def test_full_profile(self):
        got = self.labels({"ci": "github", "tracker": "github",
                           "features": ["ci-agents", "dispatch", "split", "team-tasks"]})
        roles = {f"agent:{r}" for r in ("designer", "frontend", "backend", "optimizer", "devops", "security", "writer")}
        self.assertEqual(got, roles | {"agent:team", "agent:split", "hold", "alignment-needed", "request", "ai-review",
                                       "runner:claude", "runner:opencode", "runner:codex"})

    def test_only_the_roles_of_the_project(self):
        got = self.labels({"ci": "github", "tracker": "github", "features": ["ci-agents"],
                           "roles": ["backend", "devops"]})
        self.assertEqual({g for g in got if g.startswith("agent:")}, {"agent:backend", "agent:devops"})
        self.assertNotIn("hold", got)                           # no dispatch feature


class SpecSyncHook(unittest.TestCase):
    """The local spec-sync: a merge on main that changes docs/design/ creates the issues."""

    def setUp(self):
        self.p = Project(self, {"ci": "none", "tracker": "local", "features": ["spec-sync"]})
        put(self.p.path(".agent-team", "config.json"), json.dumps({"tracker": "local", "starter": "print"}))
        put(self.p.path(".gitignore"), "docs/tasks/\n.fake-bin/\n.record\n")
        self.p.git("add", "-A")
        self.p.git("commit", "-q", "-m", "project")
        for name in ("post-merge", "post-commit"):            # as scripts/git-hooks/spec-sync.sh says
            os.symlink("../../scripts/git-hooks/spec-sync.sh", self.p.path(".git", "hooks", name))

    def tasks(self):
        d = self.p.path("docs", "tasks")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def test_merge_on_main_creates_the_issues(self):
        self.p.git("checkout", "-q", "-b", "design/shell")
        put(self.p.path("docs", "design", "shell.md"), SPEC)
        self.p.git("add", "-A")
        self.p.git("commit", "-q", "-m", "design: shell")
        self.assertEqual(self.tasks(), [])                     # not on main: nothing
        self.p.git("checkout", "-q", "main")
        r = self.p.git("merge", "-q", "--no-ff", "-m", "merge design", "design/shell")
        self.assertIn("spec-sync: docs/design/ changed on main", r.stdout + r.stderr)
        self.assertEqual(len(self.tasks()), 2, r.stdout + r.stderr)
        r = self.p.git("commit", "-q", "--allow-empty", "-m", "unrelated")
        self.assertNotIn("spec-sync", r.stdout + r.stderr)     # docs/design/ unchanged

    def test_failure_never_blocks_git(self):
        put(self.p.path(".agent-team", "config.json"), "{not json")
        put(self.p.path("docs", "design", "shell.md"), SPEC)
        self.p.git("add", "-A")
        r = self.p.git("commit", "-q", "-m", "design: shell")   # check=True: the commit succeeds
        self.assertIn("spec-sync", r.stderr)


class Skills(unittest.TestCase):
    def test_install_skills_for_each_harness(self):
        p = Project(self, {"harnesses": ["claude", "codex", "opencode"], "ci": "none", "tracker": "local"})
        p.fake("npx")
        rc, out = p.run("bash", "scripts/install-skills.sh")
        self.assertEqual(rc, 0, out)
        calls = p.calls()
        self.assertTrue(calls)
        for c in calls:
            with self.subTest(call=c):
                self.assertTrue(c.startswith("skills add "), c)
                self.assertIn("-a claude-code -a codex -a opencode", c)
                self.assertTrue(c.endswith(" -y"), c)

    def test_install_skills_claude_only(self):
        p = Project(self, {"harnesses": ["claude"], "ci": "none", "tracker": "local"})
        p.fake("npx")
        self.assertEqual(p.run("bash", "scripts/install-skills.sh")[0], 0)
        self.assertTrue(all(" -a claude-code -y" in c and "codex" not in c for c in p.calls()))

    def test_check_skills(self):
        p = Project(self, {"harnesses": ["claude"], "ci": "none", "tracker": "local"})
        rc, out = p.run("bash", "scripts/check-skills.sh")
        self.assertEqual(rc, 1, out)                          # nothing installed yet: the preloaded skills are missing
        missing = sorted({line.split("'")[1] for line in out.splitlines() if line.startswith("MISSING")})
        self.assertTrue(missing)
        for s in missing:                                     # what install-skills.sh would add
            put(p.path(".claude", "skills", s, "SKILL.md"), f"---\nname: {s}\n---\n")
        put(p.path(".claude", "skills", missing[0], "scripts", "run.sh"), "echo\n")
        rc, out = p.run("bash", "scripts/check-skills.sh")
        self.assertEqual(rc, 0, out)
        self.assertIn("OK: every preloaded skill is installed", out)
        self.assertIn(f".claude/skills/{missing[0]}/scripts/run.sh", out)

    def test_install_skills_installs_what_the_agents_preload(self):
        """Every skill an agent preloads is one install-skills.sh installs, or one the template ships."""
        p = Project(self, {"harnesses": ["claude"], "ci": "none", "tracker": "local"})
        p.fake("npx")
        p.run("bash", "scripts/install-skills.sh")
        installed = set()
        for c in p.calls():
            args = c.split()
            installed |= {args[i + 1] for i, a in enumerate(args) if a == "-s"}
        rc, out = p.run("bash", "scripts/check-skills.sh")
        missing = {line.split("'")[1] for line in out.splitlines() if line.startswith("MISSING")}
        self.assertEqual(missing - installed, set())


SCHEMA = shutil.which(os.environ.get("CHECK_JSONSCHEMA_BIN") or "check-jsonschema")


FAKE_FORGE = r"""#!/usr/bin/env python3
# gh and glab, answering from $STATE and recording every call in $RECORD
import json, os, re, sys
a = sys.argv[1:]
st = json.load(open(os.environ["STATE"]))
open(os.environ["RECORD"], "a").write(os.path.basename(sys.argv[0]) + " " + " ".join(a) + "\n")
def labels(n):
    return st["issues"].get(str(n), [])
if a[:2] == ["pr", "view"]:
    print(json.dumps(st["prs"][a[2]]))
elif a[:2] == ["pr", "list"]:
    n = int(re.search(r"\.number == (\d+)", a[a.index("--jq") + 1]).group(1))
    for num, p in st["prs"].items():
        if any(c["number"] == n for c in p["closingIssuesReferences"]):
            print(num, p["headRefName"]); break
elif a[:2] == ["issue", "view"] and "--output" in a:
    print(json.dumps({"labels": labels(a[2])}))
elif a[:2] == ["issue", "view"]:
    print("\n".join(labels(a[2])))
"""


class AgentOwner(unittest.TestCase):
    """ci/agent-owner.sh: the agent that starts a task is the only one that works on it."""

    def owner(self, state, *args, **env):
        p = Project(self, {"ci": "github", "tracker": "github", "features": ["ci-agents"]})
        for name in ("gh", "glab"):
            put(os.path.join(p.bin, name), FAKE_FORGE, 0o755)
        put(p.path(".state.json"), json.dumps(state))
        e = dict(p.env, STATE=p.path(".state.json"), DEFAULT_RUNNER="claude", **env)
        r = subprocess.run(["bash", "ci/agent-owner.sh", *args], cwd=p.dir, env=e, capture_output=True, text=True)
        out = dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)
        return r.returncode, out, r.stdout + r.stderr, p.calls()

    def test_a_task_records_its_tool(self):
        rc, out, log, calls = self.owner({"issues": {"5": ["agent:writer"]}, "prs": {}}, "github",
                                         EVENT="issues", NUMBER="5", LABEL="agent:writer", RECORD_RUNNER="1",
                                         RUNNERS='{"agent:writer":"opencode"}')
        self.assertEqual(rc, 0, log)
        self.assertEqual((out["role"], out["runner"], out["issue"], out["mode"]), ("writer", "opencode", "5", "task"))
        self.assertIn("gh issue edit 5 --add-label runner:opencode", calls)

    def test_a_request_is_flagged(self):
        """An issue with the request label has no spec: the prompts follow docs/agents/requests.md."""
        for labels, want in ((["agent:team", "request"], "true"), (["agent:team"], "false")):
            with self.subTest(labels=labels):
                rc, out, log, _ = self.owner({"issues": {"5": labels}, "prs": {}}, "github",
                                             EVENT="issues", NUMBER="5", LABEL="agent:team")
                self.assertEqual((rc, out["role"], out["request"]), (0, "team", want), log)

    def test_the_recorded_tool_wins(self):
        """Changing AGENT_RUNNERS does not move a task that has started."""
        rc, out, log, calls = self.owner({"issues": {"5": ["agent:writer", "runner:claude"]}, "prs": {}}, "github",
                                         EVENT="issues", NUMBER="5", LABEL="agent:writer", RECORD_RUNNER="1",
                                         RUNNERS='{"agent:writer":"opencode"}')
        self.assertEqual(out["runner"], "claude", log)
        self.assertFalse([c for c in calls if "edit" in c], calls)

    def test_a_comment_on_the_pull_request_reaches_its_owner(self):
        state = {"issues": {"5": ["agent:writer", "runner:opencode"]},
                 "prs": {"9": {"headRefName": "feat/5-guide", "isCrossRepository": False,
                               "closingIssuesReferences": [{"number": 5}]}}}
        rc, out, log, _ = self.owner(state, "github", EVENT="issue_comment", NUMBER="9", IS_PR="true")
        self.assertEqual(rc, 0, log)
        self.assertEqual((out["role"], out["runner"], out["issue"], out["pr"], out["branch"], out["mode"]),
                         ("writer", "opencode", "5", "9", "feat/5-guide", "iterate"))
        rc, out, log, _ = self.owner(state, "github", EVENT="issue_comment", NUMBER="5", IS_PR="false")
        self.assertEqual((out["pr"], out["branch"]), ("9", "feat/5-guide"), log)

    def test_nobody_owns_it(self):
        prs = {"9": {"headRefName": "fix", "isCrossRepository": False, "closingIssuesReferences": []},
               "10": {"headRefName": "x", "isCrossRepository": True, "closingIssuesReferences": [{"number": 5}]}}
        state = {"issues": {"5": ["agent:backend"], "6": ["bug"]}, "prs": prs}
        for number, is_pr, why in (("9", "true", "closes no issue"), ("10", "true", "fork"),
                                   ("6", "false", "no agent:<role> label")):
            with self.subTest(number=number):
                rc, out, log, _ = self.owner(state, "github", EVENT="issue_comment", NUMBER=number, IS_PR=is_pr)
                self.assertEqual(rc, 0, log)
                self.assertNotIn("role", out)
                self.assertIn(why, out["why"])

    def test_gitlab_stops_another_tool_or_role(self):
        state = {"issues": {"5": ["agent:writer", "runner:opencode"], "6": ["agent:backend"]}, "prs": {}}
        rc, _, log, _ = self.owner(state, "gitlab", "claude", TASK_ID="5")
        self.assertEqual(rc, 1, log)
        self.assertIn("AI_FLOW_HARNESS=opencode", log)
        rc, _, log, _ = self.owner(state, "gitlab", "opencode", TASK_ID="5", AI_FLOW_ROLE="backend")
        self.assertEqual(rc, 1, log)
        rc, _, log, calls = self.owner(state, "gitlab", "codex", TASK_ID="6")
        self.assertEqual((rc, log.strip()), (0, "backend"))
        self.assertIn("glab issue update 6 --label runner:codex", calls)


@unittest.skipUnless(SCHEMA, "check-jsonschema not installed")
class GitHubFiles(unittest.TestCase):
    def test_dependabot(self):
        r = subprocess.run([SCHEMA, "--builtin-schema", "vendor.dependabot",
                            os.path.join(TEMPLATE, ".github", "dependabot.yml")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_workflows(self):
        for d in (os.path.join(TEMPLATE, ".github", "workflows"), os.path.join(ROOT, ".github", "workflows")):
            files = [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".yml")]
            r = subprocess.run([SCHEMA, "--builtin-schema", "vendor.github-workflows", *files],
                               capture_output=True, text=True)
            with self.subTest(dir=d):
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
