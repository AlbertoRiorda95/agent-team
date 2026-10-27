#!/usr/bin/env python3
"""Build docs/manual.html from the Markdown chapters in docs/manual/.

The Markdown files are the source; the HTML is generated and never edited by
hand. It records a hash of the sources it was built from, so a stale HTML is
caught even where the Markdown library differs:

  python3 scripts/build_manual.py           write docs/manual.html
  python3 scripts/build_manual.py --check   exit 1 if docs/manual.html was not built
                                            from the current Markdown (CI, pre-commit)

Needs Python-Markdown, pinned so that every build gives the same bytes:
  pip install markdown==3.11.2

Links between chapters are written for GitHub ("05-scenario-local.md#profile")
and rewritten to anchors of the single page; a link to a missing chapter or
heading fails the build.
"""
import hashlib
import html
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "docs", "manual")
OUT = os.path.join(ROOT, "docs", "manual.html")
PINNED = "3.11.2"
TITLE = "Agent team: user manual"


def sources():
    names = sorted(f for f in os.listdir(SRC) if re.match(r"\d\d-.+\.md$", f))
    return ["README.md"] + names


def source_hash(names):
    h = hashlib.sha256()
    for n in names:
        h.update(n.encode() + b"\0")
        with open(os.path.join(SRC, n), "rb") as f:
            h.update(f.read().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def key(name):
    return "c00" if name == "README.md" else "c" + name[:2]


def build(names):
    import markdown
    chapters, ids = [], set()
    for n in names:
        text = open(os.path.join(SRC, n), encoding="utf-8").read()
        md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"])
        body = md.convert(text)
        k = key(n)
        body = re.sub(r'id="([^"]+)"', lambda m: f'id="{k}-{m.group(1)}"', body)
        title = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
        heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body, re.S)
        ids |= set(re.findall(r'id="([^"]+)"', body)) | {k}
        chapters.append({"name": n, "key": k, "body": body,
                         "title": re.sub("<[^>]+>", "", title.group(1)) if title else n, "heads": heads})
    files = {c["name"]: c["key"] for c in chapters}
    errors = []

    def link(m, here):
        href = m.group(1)
        if re.match(r"^[a-z]+:|^//", href):
            return m.group(0)
        target, _, frag = href.partition("#")
        if not target:
            new = f"#{here}-{frag}"
        elif target in files:
            new = f"#{files[target]}-{frag}" if frag else f"#{files[target]}"
        else:
            errors.append(f"{here}: link to {href} (not a chapter of the manual)")
            return m.group(0)
        if new[1:] not in ids:
            errors.append(f"{here}: link to {href}: no such heading")
        return f'href="{new}"'

    for c in chapters:
        c["body"] = re.sub(r'href="([^"]+)"', lambda m: link(m, c["key"]), c["body"])
        c["body"] = re.sub(r"(<table>.*?</table>)", r'<div class="table">\1</div>', c["body"], flags=re.S)
    if errors:
        raise SystemExit("broken links:\n  " + "\n  ".join(errors))
    return chapters


CSS = """
:root{--bg:#fbfaf8;--panel:#f3f1ec;--text:#1f1d1a;--muted:#6b665d;--line:#e2ddd3;--accent:#b4532a;
--accent-soft:#f6e7df;--code:#f0ede6;--link:#9a4320}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171614;--panel:#1f1d1a;--text:#ece8e1;
--muted:#a39d92;--line:#2f2c27;--accent:#e08a5f;--accent-soft:#3a271d;--code:#26231f;--link:#f0a47c}}
:root[data-theme="dark"]{--bg:#171614;--panel:#1f1d1a;--text:#ece8e1;--muted:#a39d92;--line:#2f2c27;
--accent:#e08a5f;--accent-soft:#3a271d;--code:#26231f;--link:#f0a47c}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:16px}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 ui-sans-serif,system-ui,-apple-system,
"Segoe UI",Roboto,sans-serif;-webkit-text-size-adjust:100%}
.layout{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:100vh}
nav{position:sticky;top:0;height:100vh;overflow:auto;background:var(--panel);border-right:1px solid var(--line);
padding:24px 18px}
nav .brand{font-weight:700;font-size:15px;letter-spacing:.02em;margin:0 0 4px}
nav .sub{color:var(--muted);font-size:13px;margin:0 0 18px}
nav ol{list-style:none;margin:0;padding:0}
nav li{margin:0}
nav a{display:block;color:var(--text);text-decoration:none;font-size:14px;padding:5px 8px;border-radius:6px}
nav a:hover{background:var(--accent-soft)}
nav ol ol a{color:var(--muted);font-size:13px;padding:3px 8px 3px 20px}
main{max-width:860px;padding:40px 48px 96px;width:100%}
section.chapter{padding-top:8px;margin-bottom:56px}
section.chapter+section.chapter{border-top:1px solid var(--line);padding-top:40px}
h1{font-size:32px;line-height:1.2;margin:0 0 18px;letter-spacing:-.01em}
h2{font-size:23px;margin:40px 0 12px;line-height:1.3}
h3{font-size:18px;margin:28px 0 8px}
p,ul,ol{margin:0 0 14px}
li{margin:3px 0}
a{color:var(--link)}
code{font:13.5px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--code);
padding:1px 5px;border-radius:4px}
pre{background:var(--code);padding:14px 16px;border-radius:8px;overflow-x:auto;margin:0 0 16px;
border:1px solid var(--line)}
pre code{background:none;padding:0;font-size:13px}
.table{overflow-x:auto;margin:0 0 18px;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:14.5px}
th,td{text-align:left;vertical-align:top;padding:8px 12px;border-bottom:1px solid var(--line)}
th{background:var(--panel);font-weight:600}
tr:last-child td{border-bottom:0}
.meta{color:var(--muted);font-size:13px;margin-top:64px;border-top:1px solid var(--line);padding-top:16px}
.toggle{display:none}
@media (max-width:900px){
.layout{display:block}
nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line);padding:16px}
nav ol ol{display:none}
main{padding:24px 16px 64px}
h1{font-size:26px}
}
"""


def render(chapters, digest, version):
    nav = []
    for c in chapters:
        sub = "".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in c["heads"])
        nav.append(f'<li><a href="#{c["key"]}">{c["title"]}</a>' + (f"<ol>{sub}</ol>" if sub else "") + "</li>")
    body = "\n".join(f'<section class="chapter" id="{c["key"]}">\n{c["body"]}\n</section>' for c in chapters)
    return f"""<!DOCTYPE html>
<!-- Generated from docs/manual/*.md by scripts/build_manual.py: do not edit by hand. -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="manual-source" content="sha256:{digest}">
<meta name="manual-builder" content="python-markdown {html.escape(version)}">
<title>{TITLE}</title>
<style>{CSS}</style>
</head>
<body>
<div class="layout">
<nav aria-label="Contents">
<p class="brand">Agent team</p>
<p class="sub">User manual</p>
<ol>{''.join(nav)}</ol>
</nav>
<main>
{body}
<p class="meta">Generated from the Markdown sources in <code>docs/manual/</code>.</p>
</main>
</div>
</body>
</html>
"""


def main(argv):
    names = sources()
    digest = source_hash(names)
    if "--check" in argv:
        if not os.path.exists(OUT):
            print("docs/manual.html is missing: run python3 scripts/build_manual.py")
            return 1
        m = re.search(r'name="manual-source" content="sha256:([0-9a-f]+)"', open(OUT, encoding="utf-8").read())
        if not m or m.group(1) != digest:
            print("docs/manual.html is not built from the current docs/manual/*.md: "
                  "run python3 scripts/build_manual.py and commit the result")
            return 1
        print("docs/manual.html matches docs/manual/*.md")
        return 0
    import markdown
    if markdown.__version__ != PINNED:
        print(f"note: Python-Markdown {markdown.__version__}, pinned {PINNED}: the HTML may differ in details "
              f"(pip install markdown=={PINNED})", file=sys.stderr)
    chapters = build(names)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(chapters, digest, markdown.__version__))
    print(f"wrote docs/manual.html from {len(names)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
