#!/usr/bin/env python3
"""Upgrade from the released plugin to this one, as a user does it: the project
is installed by the released template_sync.py from the released template
(main, else the latest v* tag), customized as setup does, then upgraded by
this template_sync.py to this template.

Skipped when no released version is in the Git history (a shallow checkout).
Run: python3 tests/test_upgrade.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROFILE = {"harnesses": ["claude", "codex"], "ci": "github", "tracker": "github",
           "features": ["ci-agents", "dispatch", "split"]}


def git(*args):
    r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def released():
    """The released version to upgrade from, if its template or scripts differ from this tree."""
    for ref in ("origin/main", "main", git("describe", "--tags", "--abbrev=0", "--match", "v*")):
        if ref and git("rev-parse", "--verify", "--quiet", ref + "^{commit}"):
            if git("diff", "--quiet", ref, "--", "template", "scripts") is None:     # exit 1: they differ
                return ref
    return None


REF = released()


def read(path):
    with open(path) as f:
        return f.read()


@unittest.skipUnless(REF, "no released version in the Git history")
class UpgradeFromRelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        old = os.path.join(cls.tmp, "old")
        os.makedirs(old)
        archive = subprocess.run(["git", "-C", ROOT, "archive", REF, "template", "scripts"], capture_output=True, check=True)
        subprocess.run(["tar", "-x", "-C", old], input=archive.stdout, check=True)
        cls.proj = os.path.join(cls.tmp, "proj")
        os.makedirs(cls.proj)
        subprocess.run(["git", "init", "-q", cls.proj], check=True)
        prof = os.path.join(cls.tmp, "profile.json")
        with open(prof, "w") as f:
            json.dump(PROFILE, f)
        r = subprocess.run([sys.executable, os.path.join(old, "scripts/template_sync.py"), "install", "--template",
                            os.path.join(old, "template"), "--project", cls.proj, "--profile", prof],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        # what setup does: fill in the stack and commands, add the project's own files
        agents = os.path.join(cls.proj, "AGENTS.md")
        text = read(agents).replace("<frameworks, languages, build and test commands>", "TypeScript 5, Node 24, Fastify")
        text = text.replace("- Test: `npm test`", "- Test: `npm run test:unit`")
        with open(agents, "w") as f:
            f.write(text)
        os.makedirs(os.path.join(cls.proj, "src"))
        with open(os.path.join(cls.proj, "src", "app.ts"), "w") as f:
            f.write("export const app = 1\n")
        cls.sync = [sys.executable, os.path.join(ROOT, "scripts/template_sync.py")]
        cls.status = cls.run_sync("status", "--json")
        cls.apply = cls.run_sync("apply")

    @classmethod
    def run_sync(cls, *args):
        return subprocess.run(cls.sync + [args[0], "--template", os.path.join(ROOT, "template"), "--project", cls.proj,
                                          *args[1:]], capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_status_reads_the_old_manifest(self):
        self.assertEqual(self.status.returncode, 0, self.status.stderr)
        kinds = {f["path"]: f["kind"] for f in json.loads(self.status.stdout)["files"]}
        self.assertEqual(kinds.get("AGENTS.md"), "merge")

    def test_apply_without_conflicts(self):
        self.assertEqual(self.apply.returncode, 0, self.apply.stdout + self.apply.stderr)
        for d, _, files in os.walk(self.proj):
            if "/.git" in d or "/.agent-team" in d:
                continue
            for f in files:
                p = os.path.join(d, f)
                try:
                    text = read(p)
                except UnicodeDecodeError:
                    continue
                with self.subTest(file=os.path.relpath(p, self.proj)):
                    self.assertNotIn("<<<<<<< project", text)

    def test_customizations_kept(self):
        text = read(os.path.join(self.proj, "AGENTS.md"))
        self.assertIn("TypeScript 5, Node 24, Fastify", text)
        self.assertIn("- Test: `npm run test:unit`", text)
        self.assertTrue(os.path.exists(os.path.join(self.proj, "src", "app.ts")))

    def test_new_files_arrive(self):
        for rel in ("ci/registry.sh", "scripts/hooks/block-infra-commands.sh", "scripts/hooks/writer-writes.sh"):
            p = os.path.join(self.proj, rel)
            with self.subTest(file=rel):
                self.assertTrue(os.path.exists(p))
                self.assertTrue(os.access(p, os.X_OK))
        # a profile without "roles" gets the writer role (CHANGELOG, upgrade notes)
        self.assertTrue(os.path.exists(os.path.join(self.proj, "docs/roles/writer.md")))

    def test_second_status_is_clean(self):
        r = self.run_sync("status", "--json")
        pending = [f for f in json.loads(r.stdout)["files"] if f["kind"] in ("add", "update", "merge")]
        self.assertEqual(pending, [])


if __name__ == "__main__":
    unittest.main()
