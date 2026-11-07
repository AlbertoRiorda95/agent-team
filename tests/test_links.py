#!/usr/bin/env python3
"""Every external link of the documentation answers (the manual, the README,
the CHANGELOG and the template's Markdown files). Examples and placeholders
(example.com, localhost, org/...) are not links to follow.

Needs the network; skipped without it (or with LINKS_OFFLINE=1).
Run: python3 tests/test_links.py
"""
import glob
import os
import re
import unittest
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
URL = re.compile(r"https?://[^\s)>`\"'|\]]+")
PLACEHOLDER = re.compile(r"https?://([^/]*\b(example|localhost|127\.0\.0\.1)\b|github\.com/org/|[^/]*<)")
# answer only to a package manager: the address is right, a browser gets an error
NOT_PAGES = ("https://npm.pkg.github.com",)


def links():
    files = [os.path.join(ROOT, f) for f in ("README.md", "CHANGELOG.md")]
    files += glob.glob(os.path.join(ROOT, "docs/manual/*.md"))
    files += glob.glob(os.path.join(ROOT, "template/**/*.md"), recursive=True, include_hidden=True)
    found = {}
    for f in files:
        with open(f) as fh:
            for n, line in enumerate(fh, 1):
                for url in URL.findall(line):
                    url = url.rstrip(".,:;")
                    if not PLACEHOLDER.match(url) and url not in NOT_PAGES:
                        found.setdefault(url, f"{os.path.relpath(f, ROOT)}:{n}")
    return found


def status(url):
    req = urllib.request.Request(url, headers={"User-Agent": "agent-team-link-check"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def online():
    try:
        return status("https://github.com") < 500
    except OSError:
        return False


@unittest.skipUnless(os.environ.get("LINKS_OFFLINE") != "1" and online(), "no network")
class Links(unittest.TestCase):
    def test_links(self):
        for url, where in sorted(links().items()):
            with self.subTest(url=url, at=where):
                try:
                    code = status(url)
                except OSError as e:
                    self.fail(f"{url}: {e}")
                # 429: rate limited, the page exists
                self.assertTrue(code < 400 or code == 429, f"{url}: HTTP {code} ({where})")


if __name__ == "__main__":
    unittest.main()
