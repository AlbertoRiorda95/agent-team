"""Local tracker: one Markdown file per issue in the repository (default docs/tasks/),
for the local scenario without a platform, and for tests.

    docs/tasks/012-orders-date-filter.md
    ---
    id: 12
    title: "Orders · 2/3 · backend: Implement the filter"
    state: open                 open | done | dropped
    milestone: "M1 · Orders"
    labels: ["agent:backend"]
    parent: 10
    depends: [11]
    ---
    <body>
    <!-- comments -->
    <!-- comment by="alberto" -->
    <text>

Milestones are in docs/tasks/_milestones.json. Edit the files by hand as you like:
"state: done" closes a task. Comments are trusted (there is no other author).
"""
import json
import os
import re
import subprocess

from .. import core

SEP = "<!-- comments -->"


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:48] or "task"


class Adapter(core.Tracker):
    name = "local"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.dir = (cfg.get("local") or {}).get("dir") or "docs/tasks"

    # ---- files
    def _files(self):
        if not os.path.isdir(self.dir):
            return []
        return sorted(os.path.join(self.dir, f) for f in os.listdir(self.dir)
                      if f.endswith(".md") and re.match(r"\d+-", f))

    def _read(self, path):
        text = open(path, encoding="utf-8").read()
        m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
        if not m:
            raise core.TrackerError(f"{path}: missing front matter")
        meta = {}
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            v = v.strip()
            if not k.strip():
                continue
            try:
                meta[k.strip()] = json.loads(v) if v else None
            except ValueError:
                meta[k.strip()] = v
        rest = m.group(2)
        body, _, comments = rest.partition(SEP)
        return meta, body.strip("\n"), comments, path

    def _write(self, meta, body, comments, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        lines = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items()] + ["---", body.rstrip("\n"), ""]
        if comments.strip():
            lines += [SEP + comments.rstrip("\n"), ""]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _path(self, ref):
        for p in self._files():
            if int(os.path.basename(p).split("-", 1)[0]) == int(str(ref).lstrip("#")):
                return p
        raise core.TrackerError(f"local issue not found: {ref}")

    def _issue(self, meta, body, path):
        state = meta.get("state") or "open"
        return core.Issue(meta["id"], f"#{meta['id']}", meta.get("title"), body, open=state == "open",
                          done=state == "done", labels=meta.get("labels") or [], milestone=meta.get("milestone"),
                          parent=str(meta["parent"]) if meta.get("parent") else None, url=path,
                          extra={"depends": [str(d) for d in meta.get("depends") or []]})

    # ---- read
    def issues(self):
        out = []
        for p in self._files():
            meta, body, _, _ = self._read(p)
            out.append(self._issue(meta, body, p))
        return out

    def get(self, ref):
        meta, body, _, p = self._read(self._path(ref))
        return self._issue(meta, body, p)

    def _ms_file(self):
        return os.path.join(self.dir, "_milestones.json")

    def milestones(self):
        if not os.path.exists(self._ms_file()):
            return {}
        rows = json.load(open(self._ms_file(), encoding="utf-8"))
        return {core.code(m["title"]): (m["title"], m["title"]) for m in rows}

    def children(self, parent):
        return [i for i in self.issues() if i.parent == parent.ref]

    def blockers(self, issue):
        return list(issue.extra.get("depends", []))

    def comments(self, issue):
        _, _, comments, _ = self._read(self._path(issue.ref))
        out = []
        for m in re.finditer(r'<!-- comment by="([^"]*)" -->\n(.*?)(?=<!-- comment by=|\Z)', comments, re.S):
            out.append(core.Comment(m.group(2).strip("\n"), m.group(1), mine=True))
        return out

    def me(self):
        p = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
        return p.stdout.strip() or "me"

    # ---- write
    def create_milestone(self, title, description):
        rows = json.load(open(self._ms_file(), encoding="utf-8")) if os.path.exists(self._ms_file()) else []
        rows.append({"title": title, "description": description})
        os.makedirs(self.dir, exist_ok=True)
        with open(self._ms_file(), "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
            f.write("\n")
        return title

    def create_issue(self, title, body, milestone=None, parent=None):
        ids = [int(os.path.basename(p).split("-", 1)[0]) for p in self._files()]
        n = max(ids, default=0) + 1
        meta = {"id": n, "title": title, "state": "open", "milestone": milestone, "labels": [],
                "parent": int(parent.ref) if parent is not None else None, "depends": []}
        path = os.path.join(self.dir, f"{n:03d}-{_slug(title)}.md")
        self._write(meta, body, "", path)
        return self._issue(meta, body, path)

    def _update(self, issue, fn):
        meta, body, comments, path = self._read(self._path(issue.ref))
        fn(meta)
        self._write(meta, body, comments, path)

    def set_milestone(self, issue, milestone_ref):
        self._update(issue, lambda m: m.__setitem__("milestone", milestone_ref))

    def edit_issue(self, issue, title, body):
        meta, _, comments, path = self._read(self._path(issue.ref))
        meta["title"] = title
        self._write(meta, body, comments, path)

    def link_child(self, parent, child):
        self._update(child, lambda m: m.__setitem__("parent", int(parent.ref)))

    def unlink_child(self, parent, child):
        self._update(child, lambda m: m.__setitem__("parent", None))

    def add_dependency(self, issue, blocker):
        def f(m):
            deps = [int(d) for d in m.get("depends") or []]
            if int(blocker.ref) not in deps:
                deps.append(int(blocker.ref))
            m["depends"] = deps
        self._update(issue, f)
        return True

    def comment(self, issue, body):
        meta, text, comments, path = self._read(self._path(issue.ref))
        comments = comments.rstrip("\n") + f'\n<!-- comment by="{self.me()}" -->\n{body.rstrip()}\n'
        self._write(meta, text, comments, path)

    def add_label(self, issue, label):
        self._update(issue, lambda m: m.__setitem__("labels", sorted(set((m.get("labels") or []) + [label]))))

    def remove_label(self, issue, label):
        self._update(issue, lambda m: m.__setitem__("labels", [l for l in m.get("labels") or [] if l != label]))

    def check(self):
        return [(True, f"local tracker in {self.dir}: {len(self.issues())} issues, {len(self.milestones())} milestones")]
