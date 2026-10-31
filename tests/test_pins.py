#!/usr/bin/env python3
"""Every action pinned to a commit SHA exists, and is the release its comment names
(`uses: owner/repo@<sha>  # v6.1.0`): a tag of that version points to the commit.

Needs the network (git ls-remote against github.com); skipped without it.
Run: python3 tests/test_pins.py
"""
import glob
import os
import re
import subprocess
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
USES = re.compile(r"uses:\s*([\w.-]+/[\w.-]+)(?:/[^@\s]*)?@([0-9a-f]{40})(?:\s*#\s*(\S+))?")


def pins():
    found = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "template/.github/workflows/*.yml")) +
                    glob.glob(os.path.join(ROOT, ".github/workflows/*.yml"))):
        with open(f) as fh:
            for n, line in enumerate(fh, 1):
                m = USES.search(line)
                if m:
                    found.setdefault((m.group(1), m.group(2), m.group(3)), []).append(f"{os.path.relpath(f, ROOT)}:{n}")
    return found


def tags(repo):
    r = subprocess.run(["git", "ls-remote", "--tags", f"https://github.com/{repo}"], capture_output=True, text=True,
                       timeout=60, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    if r.returncode != 0:
        return None
    out = {}
    for line in r.stdout.splitlines():
        sha, ref = line.split("\t")
        name = ref[len("refs/tags/"):]
        if name.endswith("^{}"):
            out[name[:-3]] = sha              # the commit an annotated tag points to
        else:
            out.setdefault(name, sha)
    return out


def online():
    return tags("actions/checkout") is not None


@unittest.skipUnless(os.environ.get("PINS_OFFLINE") != "1" and online(), "no network")
class Pins(unittest.TestCase):
    def test_pins(self):
        cache = {}
        for (repo, sha, version), where in pins().items():
            with self.subTest(action=repo, sha=sha, at=where[0]):
                if repo not in cache:
                    cache[repo] = tags(repo)
                t = cache[repo]
                self.assertIsNotNone(t, f"{repo}: not reachable")
                self.assertIsNotNone(version, f"{repo}@{sha}: no '# vX' comment naming the release")
                at = {n for n, s in t.items() if s == sha}
                self.assertTrue(at, f"{repo}@{sha}: no tag points to this commit ({', '.join(where)})")
                self.assertIn(version, at, f"{repo}@{sha} is {sorted(at)}, the comment says {version}")


if __name__ == "__main__":
    unittest.main()
