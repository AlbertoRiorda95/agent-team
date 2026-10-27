"""Roadmap and specs in docs/design/ -> the milestones and task issues to create.

Every planned issue carries a stable key ("key: docs/design/x.md#3", or
"design:M1:login", or "docs/design/x.md#team") in a marker, so it is found again
even if its title changes (for example when rows are added to the breakdown).
"""
import glob
import os
import re

from . import core

DESIGN = "docs/design"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def front(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.split("#")[0].strip()
    return meta


def items(value):
    return [x.strip(" '\"") for x in re.split(r"[,;]", (value or "").strip("[] ")) if x.strip(" '\"")]


def md_section(text, name):
    m = re.search(r"^## " + re.escape(name) + r"\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1) if m else ""


def table(block):
    rows = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|") or re.match(r"^\|[\s:|-]+\|$", line):
            continue
        rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows[1:] if rows else []


def load_spec(path):
    text = open(path, encoding="utf-8").read()
    meta = front(text)
    if meta.get("ready") != "yes":
        return None
    title = re.search(r"^# (.+)$", text, re.M)
    title = re.sub(r"\s+[—-]\s+.*$", "", title.group(1)).strip() if title else os.path.basename(path)
    block = md_section(text, "Task breakdown")
    rows = [r for r in table(block) if len(r) >= 3 and r[0].strip().isdigit() and r[2] not in ("", "...")]
    team = re.search(r"Team task possible:\s*yes\b.*?roles?:\s*([^)]+)\)", block, re.I | re.S)
    return {"path": path, "title": title, "rows": rows,
            "slug": slug(os.path.splitext(os.path.basename(path))[0]),
            "milestone": meta.get("milestone", ""), "features": items(meta.get("features", "")),
            "team_roles": [x for x in items(team.group(1).replace("\n", " ")) if x.lower() in core.ROLES] if team else None}


def load_roadmap():
    path = os.path.join(DESIGN, "project.md")
    if not os.path.exists(path):
        return []
    out = []
    for r in table(md_section(open(path, encoding="utf-8").read(), "Roadmap")):
        if len(r) >= 2 and r[0] not in ("", "..."):
            out.append((r[0], [f for f in items(r[1]) if f != "..."]))
    return out


def tracked(r):
    """The Issue column: None (create), 'done', or an issue id ("12", "PROJ-12")."""
    v = r[4].strip() if len(r) > 4 else ""
    if v in ("", "-", "—"):
        return None
    m = re.match(r"#?(\d+)$", v) or re.match(r"([A-Z][A-Z0-9]+-\d+)$", v)
    return m.group(1) if m else "done"


def start_line(trk, role):
    if trk.name == "redmine":
        return f"To start it, once the tasks it depends on are done: `agent:{role}`, with scripts/dispatch.py."
    return (f"To start it, add the label `agent:{role}` once the issues it depends on are done "
            f"(or let scripts/dispatch.py do it).")


def _task(key, title, body, deps=(), ref=None, legacy=None):
    return {"key": key, "title": title, "body": body, "deps": list(deps), "ref": ref, "legacy": legacy}


def task_issues(spec, team, trk):
    out = []
    mark = trk.marker(core.MARK_CREATED)
    for r in spec["rows"]:
        ref = tracked(r)
        if ref is not None:
            out.append(_task(f"{spec['path']}#{r[0].strip()}", None, None, ref=ref))
    rows = [r for r in spec["rows"] if tracked(r) is None]
    if not rows:
        return out
    if team and spec["team_roles"]:
        key = f"{spec['path']}#team"
        lines = "\n".join(f"| {r[0]} | {r[1]} | {r[2]} | {r[3] if len(r) > 3 else '-'} |" for r in rows)
        nums = ", ".join(r[0] for r in rows)
        out.append(_task(key, f"{spec['title']} · team task (tasks {nums})",
                         f"## Spec\n{spec['path']} - section: Task breakdown, rows {nums}\n\n"
                         f"## Task\nImplement these tasks of the breakdown on one branch, one PR:\n\n"
                         f"| # | Role | Task | Depends on |\n|---|---|---|---|\n{lines}\n\n"
                         f"Roles: {', '.join(spec['team_roles'])}\n\n{start_line(trk, 'team')}\n\n"
                         f"{mark}\n{trk.marker('key: ' + key)}"))
        return out
    total = len(spec["rows"])
    for r in rows:
        num, role, task = r[0].strip(), r[1].strip().lower(), r[2].strip()
        deps = re.findall(r"\d+", r[3]) if len(r) > 3 else []
        short = task if len(task) <= 70 else task[:67].rstrip() + "..."
        key = f"{spec['path']}#{num}"
        out.append(_task(key, f"{spec['title']} · {num}/{total} · {role}: {short}",
                         f"## Spec\n{spec['path']} - section: Task breakdown, row {num}\n\n"
                         f"## Task\n{task}\n\n## Depends on\n{{deps}}\n\n{start_line(trk, role)}\n\n"
                         f"{mark}\n{trk.marker('key: ' + key)}",
                         deps=[f"{spec['path']}#{d}" for d in deps],
                         legacy=(f"{spec['title']} · {num}/", f" · {role}: ")))
    return out


def build_plan(team, trk):
    """[(milestone or None, [task])]; milestone = (code, title, description)."""
    specs = [s for s in (load_spec(p) for p in sorted(glob.glob(os.path.join(DESIGN, "*.md")))
                         if not os.path.basename(p).startswith("_")
                         and os.path.basename(p) not in ("project.md", "README.md")) if s]
    used, groups = set(), []
    mark = trk.marker(core.MARK_CREATED)
    for milestone, feats in load_roadmap():
        children = []
        for feat in feats:
            spec = next((s for s in specs if s["slug"] == slug(feat)
                         or (slug(feat) in map(slug, s["features"])
                             and (not s["milestone"] or s["milestone"] == milestone))), None)
            if spec:
                if spec["path"] not in used:
                    used.add(spec["path"])
                    children += task_issues(spec, team, trk)
                continue
            key = f"design:{milestone}:{slug(feat)}"
            children.append(_task(key, f"Design: {feat} ({milestone})",
                                  f"## Roadmap\nMilestone {milestone}, feature \"{feat}\" (docs/design/project.md).\n\n"
                                  f"## Task\nDesign this feature in a studio session with you: `/design-studio {slug(feat)}`. "
                                  f"It produces docs/design/{slug(feat)}.md; once it is ready and merged, create its "
                                  f"task issues again with scripts/create-issues.py.\n\n"
                                  f"No agent: design happens with you, not in CI.\n\n{mark}\n{trk.marker('key: ' + key)}"))
        ms = (milestone, f"{milestone} · {', '.join(feats)}"[:120],
              f"Roadmap milestone {milestone}: {', '.join(feats)} (docs/design/project.md). "
              f"Created by scripts/create-issues.py.")
        groups.append((ms, children))
    for s in specs:
        if s["path"] not in used:
            groups.append((None, task_issues(s, team, trk)))
    return groups
