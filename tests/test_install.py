#!/usr/bin/env python3
"""The plugin as a user gets it (chapter 2), with the claude CLI and a HOME of
its own: the marketplace added from a copy of the released plugin (main), the
plugin installed, then the marketplace moved to this tree and the plugin
updated. The installed copy keeps the scripts executable, and its
template_sync.py installs a project, as the setup skill does.

Skipped without the claude CLI, or without main in the Git history.
Run: python3 tests/test_install.py
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CLAUDE = shutil.which(os.environ.get("CLAUDE_BIN") or "claude")


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True)


def released():
    for ref in ("origin/main", "main"):
        if git("rev-parse", "--verify", "--quiet", ref + "^{commit}").returncode == 0:
            return ref
    return None


REF = released()


def version(path):
    with open(os.path.join(path, ".claude-plugin", "plugin.json")) as f:
        return json.load(f)["version"]


@unittest.skipUnless(CLAUDE and REF, "claude CLI not installed, or no main branch in the history")
class Install(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.home = os.path.join(cls.tmp, "home")
        cls.mkt = os.path.join(cls.tmp, "mkt")
        os.makedirs(cls.home)
        archive = subprocess.run(["git", "-C", ROOT, "archive", REF], capture_output=True, check=True).stdout
        os.makedirs(cls.mkt)
        subprocess.run(["tar", "-x", "-C", cls.mkt], input=archive, check=True)
        cls.old = version(cls.mkt)
        cls.env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC"))}
        cls.env.update(HOME=cls.home, DISABLE_AUTOUPDATER="1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
        cls.added = cls.claude("plugin", "marketplace", "add", "./mkt")
        cls.installed = cls.claude("plugin", "install", "agent-team@agent-team")
        cls.details = cls.claude("plugin", "details", "agent-team@agent-team")
        # this tree becomes the marketplace's content, as a push to the plugin's repository
        files = subprocess.run(["git", "-C", ROOT, "ls-files", "-co", "--exclude-standard", "-z"],
                               capture_output=True, check=True).stdout.decode().split("\0")
        for rel in filter(None, files):
            src, dst = os.path.join(ROOT, rel), os.path.join(cls.mkt, rel)
            if os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        cls.new = version(ROOT)
        cls.claude("plugin", "marketplace", "update", "agent-team")
        cls.updated = cls.claude("plugin", "update", "agent-team@agent-team")
        cls.listed = cls.claude("plugin", "list")

    @classmethod
    def claude(cls, *args):
        return subprocess.run([CLAUDE, *args], cwd=cls.tmp, env=cls.env, capture_output=True, text=True,
                              timeout=300, stdin=subprocess.DEVNULL)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def cache(self, v):
        return os.path.join(self.home, ".claude", "plugins", "cache", "agent-team", "agent-team", v)

    def test_install_from_the_marketplace(self):
        self.assertEqual(self.added.returncode, 0, self.added.stdout + self.added.stderr)
        self.assertEqual(self.installed.returncode, 0, self.installed.stdout + self.installed.stderr)
        self.assertIn(f"agent-team) {self.old}", self.details.stdout)
        line = re.search(r"Skills \((\d+)\)", self.details.stdout)
        self.assertIsNotNone(line, self.details.stdout)
        self.assertGreaterEqual(int(line.group(1)), 5)

    def test_update_to_this_version(self):
        self.assertEqual(self.updated.returncode, 0, self.updated.stdout + self.updated.stderr)
        self.assertIn(f"Version: {self.new}", self.listed.stdout)
        if self.new != self.old:
            self.assertIn(f"from {self.old} to {self.new}", self.updated.stdout)
        installed = self.cache(self.new)
        for d in ("skills", "template", "scripts"):
            self.assertTrue(os.path.isdir(os.path.join(installed, d)), d)
        self.assertEqual(set(os.listdir(os.path.join(installed, "skills"))), set(os.listdir(os.path.join(ROOT, "skills"))))

    def test_installed_scripts_stay_executable(self):
        installed = self.cache(self.new)
        for rel in subprocess.run(["git", "-C", ROOT, "ls-files", "-s"], capture_output=True, text=True).stdout.splitlines():
            mode, _, _, path = rel.split(None, 3)
            if mode == "100755" and os.path.exists(os.path.join(installed, path)):
                with self.subTest(file=path):
                    self.assertTrue(os.access(os.path.join(installed, path), os.X_OK))

    def test_setup_from_the_installed_plugin(self):
        installed = self.cache(self.new)
        proj = os.path.join(self.tmp, "proj")
        os.makedirs(proj)
        subprocess.run(["git", "init", "-q", proj], check=True)
        prof = os.path.join(self.tmp, "profile.json")
        with open(prof, "w") as f:
            json.dump({"harnesses": ["claude"], "ci": "github", "tracker": "github", "features": []}, f)
        r = subprocess.run(["python3", os.path.join(installed, "scripts", "template_sync.py"), "install",
                            "--template", os.path.join(installed, "template"), "--project", proj, "--profile", prof],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for hook in ("block-infra-commands.sh", "role-hooks.sh"):
            self.assertTrue(os.access(os.path.join(proj, "scripts", "hooks", hook), os.X_OK), hook)


if __name__ == "__main__":
    unittest.main()
