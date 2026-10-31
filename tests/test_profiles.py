#!/usr/bin/env python3
"""Profiles: the template rendered for different harnesses, CI, trackers and
features is consistent, and template_sync.py moves a project between profiles
(prune what leaves, restore what comes back) without losing the user's changes.

Run: python3 tests/test_profiles.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE = os.path.join(ROOT, "template")
SYNC = os.path.join(ROOT, "scripts", "template_sync.py")
sys.path.insert(0, os.path.join(TEMPLATE, "scripts"))
from agentteam import profile  # noqa: E402

PROFILES = {
    "full": {},
    "claude-github": {"harnesses": ["claude"], "ci": "github", "tracker": "github",
                      "features": ["ci-agents", "team-tasks", "split", "dispatch"]},
    "codex-jira": {"harnesses": ["codex"], "ci": "github", "tracker": "jira", "features": ["ci-agents", "spec-sync"]},
    "opencode-claude-gitlab": {"harnesses": ["opencode", "claude"], "ci": "gitlab", "tracker": "gitlab",
                               "features": ["ci-agents", "litellm", "split", "spec-sync"],
                               "roles": ["frontend", "backend", "devops"]},
    "codex-claude-github": {"harnesses": ["codex", "claude"], "ci": "github", "tracker": "github",
                            "features": ["ci-agents", "dispatch"]},
    "local-only": {"harnesses": ["claude", "codex", "opencode"], "ci": "none", "tracker": "local",
                   "features": ["spec-sync"]},
    "no-tracker": {"harnesses": ["opencode"], "ci": "none", "tracker": "none", "features": []},
}


def run(cmd, cwd=None, inp=None):
    return subprocess.run(cmd, cwd=cwd, input=inp, capture_output=True, text=True)


class Rendered(unittest.TestCase):
    """Every sample profile renders to a project whose files load and point to files that exist."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.dirs = {}
        for name, cfg in PROFILES.items():
            d = os.path.join(cls.tmp, name)
            profile.render_tree(TEMPLATE, d, cfg)
            cls.dirs[name] = d

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def files(self, d):
        return profile.walk(d)

    def test_files_load(self):
        for name, d in self.dirs.items():
            for rel in self.files(d):
                p = os.path.join(d, rel)
                text = open(p, encoding="utf-8").read() if profile.is_text(p) else ""
                with self.subTest(profile=name, file=rel):
                    self.assertNotIn(profile.LEAD, text)
                    if rel.endswith(".json"):
                        json.loads(text)
                    elif rel.endswith(".toml"):
                        tomllib.loads(text)
                    elif rel.endswith(".sh"):
                        self.assertEqual(run(["bash", "-n", p]).returncode, 0)
                    elif rel.endswith(".py"):
                        compile(open(p, encoding="utf-8").read(), p, "exec")
                    if rel.endswith((".yml", ".yaml", ".example")) and shutil.which("python3"):
                        try:
                            import yaml
                        except ImportError:
                            continue
                        if rel.endswith((".yml", ".yaml")) or rel == ".gitlab-ci.yml.example":
                            yaml.safe_load(text)

    def test_workflows_lint(self):
        if not shutil.which("actionlint"):
            self.skipTest("actionlint not installed")
        for name, d in self.dirs.items():
            wf = os.path.join(d, ".github", "workflows")
            if os.path.isdir(wf):
                r = run(["actionlint"] + sorted(os.path.join(wf, f) for f in os.listdir(wf)), cwd=d)
                self.assertEqual(r.returncode, 0, f"{name}: {r.stdout}{r.stderr}")

    def test_references_exist(self):
        for name, d in self.dirs.items():
            have = set(self.files(d))
            refs = set()
            s = os.path.join(d, ".claude", "settings.json")
            if os.path.exists(s):
                for groups in json.load(open(s))["hooks"].values():
                    for g in groups:
                        refs |= {re.sub(r'^"\$CLAUDE_PROJECT_DIR"/', "", h["command"]).split()[0] for h in g["hooks"]}
            for rel in have:
                if rel.startswith(".claude/agents/"):
                    refs |= set(re.findall(r'command: \'"\$CLAUDE_PROJECT_DIR"/([^\']+)\'', open(os.path.join(d, rel)).read()))
            h = os.path.join(d, ".codex", "hooks.json")
            if os.path.exists(h):
                for groups in json.load(open(h))["hooks"].values():
                    for g in groups:
                        refs |= {re.sub(r'^"\$\(git rev-parse --show-toplevel\)/|"$', "", x["command"]) for x in g["hooks"]}
            for doc in ("AGENTS.md", "docs/agents/README.md"):
                text = open(os.path.join(d, doc)).read()
                refs |= set(re.findall(r"`(docs/agents/[a-z-]+\.md)`", text))
                refs |= {"docs/agents/" + m for m in re.findall(r"^- `([a-z-]+\.md)`", text, re.M)}
            refs |= {"docs/roles/" + r + ".md" for r in profile.resolve(PROFILES[name])["roles"]}
            for ref in sorted(refs):
                with self.subTest(profile=name, ref=ref):
                    self.assertIn(ref, have)

    def test_what_each_profile_keeps(self):
        d = self.dirs
        self.assertTrue(os.path.exists(os.path.join(d["codex-jira"], ".codex/agents/backend.toml")))
        self.assertFalse(os.path.exists(os.path.join(d["codex-jira"], ".claude")))
        self.assertFalse(os.path.exists(os.path.join(d["codex-jira"], ".github/workflows/agents.yml")))
        self.assertTrue(os.path.exists(os.path.join(d["codex-jira"], "scripts/agentteam/trackers/jira.py")))
        self.assertFalse(os.path.exists(os.path.join(d["codex-jira"], "scripts/agentteam/trackers/github.py")))
        self.assertFalse(os.path.exists(os.path.join(d["opencode-claude-gitlab"], ".agents")))   # OpenCode reads .claude/skills
        self.assertTrue(os.path.exists(os.path.join(d["no-tracker"], ".agents/skills/handoff/SKILL.md")))
        self.assertFalse(os.path.exists(os.path.join(d["no-tracker"], "scripts/create-issues.py")))
        self.assertTrue(os.path.exists(os.path.join(d["no-tracker"], "scripts/agent-team.py")))
        oc = json.load(open(os.path.join(d["opencode-claude-gitlab"], "opencode.json")))
        self.assertIn("litellm", oc["provider"])
        oc = json.load(open(os.path.join(d["no-tracker"], "opencode.json")))
        self.assertNotIn("litellm", oc.get("provider", {}))
        agents = open(os.path.join(d["codex-jira"], "AGENTS.md")).read()
        self.assertNotIn("## Team tasks", agents)
        self.assertNotIn("Claude Code:", agents)
        self.assertIn("Codex:", agents)
        wf = open(os.path.join(d["codex-claude-github"], ".github/workflows/agents.yml")).read()
        self.assertIn("vars.AGENT_DEFAULT_RUNNER || 'codex'", wf)
        self.assertIn("  claude:\n", wf)
        self.assertNotIn("\n  team:\n", wf)
        self.assertNotIn("\n  opencode:\n", wf)
        # spec-sync: the workflow with the tracker's secrets only, the GitLab job, the local hook
        wf = open(os.path.join(d["codex-jira"], ".github/workflows/spec-sync.yml")).read()
        self.assertIn("JIRA_API_TOKEN", wf)
        self.assertNotIn("LINEAR_API_KEY", wf)
        self.assertFalse(os.path.exists(os.path.join(d["claude-github"], ".github/workflows/spec-sync.yml")))
        self.assertTrue(os.path.exists(os.path.join(d["opencode-claude-gitlab"], ".gitlab/ci/spec-sync.yml")))
        self.assertIn(".gitlab/ci/spec-sync.yml", open(os.path.join(d["opencode-claude-gitlab"], ".gitlab-ci.yml.example")).read())
        self.assertTrue(os.path.exists(os.path.join(d["local-only"], "scripts/git-hooks/spec-sync.sh")))
        self.assertFalse(os.path.exists(os.path.join(d["no-tracker"], "scripts/git-hooks/spec-sync.sh")))
        full = sum(os.path.getsize(os.path.join(d["full"], "AGENTS.md")) for _ in [0])
        small = os.path.getsize(os.path.join(d["no-tracker"], "AGENTS.md"))
        self.assertLess(small, full)


class Sync(unittest.TestCase):
    """template_sync.py: install for one profile, switch profiles, come back."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = os.path.join(self.tmp, "project")
        os.makedirs(self.p)
        run(["git", "init", "-q"], cwd=self.p)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def sync(self, *args):
        r = run([sys.executable, SYNC, *args, "--template", TEMPLATE, "--project", self.p])
        return r.returncode, r.stdout + r.stderr

    def set_profile(self, cfg):
        os.makedirs(os.path.join(self.p, ".agent-team"), exist_ok=True)
        json.dump(cfg, open(os.path.join(self.p, ".agent-team", "config.json"), "w"))

    def exists(self, rel):
        return os.path.exists(os.path.join(self.p, rel))

    def test_switch_and_back(self):
        prof = os.path.join(self.tmp, "profile.json")
        json.dump({"harnesses": ["claude"], "ci": "github", "tracker": "github",
                   "features": ["ci-agents", "split"]}, open(prof, "w"))
        rc, out = self.sync("install", "--profile", prof)
        self.assertEqual(rc, 0, out)
        self.assertTrue(self.exists(".claude/settings.json") and self.exists("scripts/agentteam/trackers/github.py"))
        self.assertFalse(self.exists(".codex") or self.exists("scripts/agentteam/trackers/jira.py"))
        self.assertTrue(self.exists(".agent-team/config.json"))

        # the user's own changes
        with open(os.path.join(self.p, "AGENTS.md"), "a") as f:
            f.write("\n## Our rule\nAlways write the changelog.\n")
        with open(os.path.join(self.p, ".claude/agents/backend.md"), "a") as f:
            f.write("\nUse the repository pattern.\n")

        # to Codex and Jira
        self.set_profile({"harnesses": ["codex"], "ci": "github", "tracker": "jira", "features": ["ci-agents"]})
        rc, out = self.sync("status")
        self.assertIn("prune", out)
        rc, out = self.sync("apply")
        self.assertEqual(rc, 0, out)
        self.assertTrue(self.exists(".codex/config.toml") and self.exists("scripts/agentteam/trackers/jira.py"))
        self.assertFalse(self.exists(".claude/settings.json") or self.exists("CLAUDE.md"))
        self.assertFalse(self.exists("scripts/agentteam/trackers/github.py"))
        self.assertTrue(self.exists(".claude/agents/backend.md"), "changed by the user: kept")
        self.assertIn("out-of-profile", self.sync("status")[1])
        agents = open(os.path.join(self.p, "AGENTS.md")).read()
        self.assertIn("Always write the changelog.", agents)
        self.assertIn("Codex:", agents)
        self.assertNotIn("Claude Code:", agents)
        self.assertNotIn("## Splitting issues", agents)

        # back to Claude
        self.set_profile({"harnesses": ["claude"], "ci": "github", "tracker": "github",
                          "features": ["ci-agents", "split"]})
        rc, out = self.sync("apply")
        self.assertEqual(rc, 0, out)
        self.assertTrue(self.exists(".claude/settings.json") and self.exists("CLAUDE.md"))
        self.assertTrue(self.exists("scripts/agentteam/trackers/github.py"))
        self.assertFalse(self.exists(".codex"))
        agents = open(os.path.join(self.p, "AGENTS.md")).read()
        self.assertIn("Always write the changelog.", agents)
        self.assertIn("Claude Code:", agents)
        self.assertIn("## Splitting issues", agents)
        self.assertIn("Use the repository pattern.", open(os.path.join(self.p, ".claude/agents/backend.md")).read())
        rc, out = self.sync("apply", "--dry-run")
        self.assertNotIn("would", out, "nothing left to do")

    def test_prune_in_a_plain_copy(self):
        shutil.rmtree(self.p)
        shutil.copytree(TEMPLATE, self.p)
        self.set_profile({"harnesses": ["codex"], "ci": "none", "tracker": "local", "features": []})
        cli = [sys.executable, os.path.join(self.p, "scripts", "agent-team.py")]
        r = run(cli + ["prune", "--dry-run"], cwd=self.p)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.exists(".claude/settings.json"))
        r = run(cli + ["prune"], cwd=self.p)
        self.assertEqual(r.returncode, 2, "a plain copy needs --yes")
        r = run(cli + ["prune", "--yes"], cwd=self.p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.exists(".claude") or self.exists(".github") or self.exists("infra"))
        self.assertTrue(self.exists(".codex/agents/backend.toml") and self.exists("scripts/agentteam/trackers/local.py"))
        self.assertNotIn("## Team tasks", open(os.path.join(self.p, "AGENTS.md")).read())
        r = run(cli + ["prune", "--dry-run"], cwd=self.p)
        self.assertIn("Nothing to prune", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
