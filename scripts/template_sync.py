#!/usr/bin/env python3
"""Install the agent-team template into a project, and upgrade it later without
losing the project's own changes.

How it stays safe:
  - It never deletes a project file and never overwrites one silently.
  - At install it keeps, under .agent-team/base/, a copy of every template file
    as it was installed: the "base". At upgrade, for each file it compares three
    versions: base (template then), project (with your changes), template (now).
      * template unchanged since base       -> nothing to do, whatever you changed
      * project unchanged since base        -> safe update to the new template
      * both changed                        -> three-way merge (git merge-file);
                                               conflicts are left marked, never guessed
  - Files the project owns after setup (README.md, docs/design-decisions.md,
    .mcp.json, docs/roles/security-scope.txt) are only created when missing.
  - The project profile (.agent-team/config.json: harnesses, CI, tracker,
    roles, features; see template/scripts/agentteam/profile.py) decides which
    template files and sections the project gets. The template is rendered for
    the profile first, so a profile change is just another upgrade: files and
    sections the new profile includes are added, and template files it no
    longer includes are removed if you did not change them ("prune"; changed
    ones are kept and listed).

Commands (run from anywhere; paths are explicit):
  template_sync.py install --template T --project P [--profile config.json] [--dry-run]
  template_sync.py status  --template T --project P [--json]
  template_sync.py apply   --template T --project P [--dry-run] [--kinds add,update,merge,prune] [--paths p1 p2 ...]
  template_sync.py record  --template T --project P --paths p1 p2 ...

`record` marks files you merged by hand as up to date with the current template
(their base becomes the current template file). Exit code 1 when `apply` leaves
merge conflicts, 2 on usage errors.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date

STATE = ".agent-team"
OWNED = {"README.md", "docs/design-decisions.md", ".mcp.json", ".claude/security-scope", "docs/roles/security-scope.txt"}
SKIP_DIRS = {".git", "__pycache__", "node_modules"}


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def template_files(root):
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for f in sorted(files):
            out.append(os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/"))
    return out


def plugin_version(template):
    p = os.path.join(template, "..", ".claude-plugin", "plugin.json")
    try:
        return json.load(open(p, encoding="utf-8")).get("version", "unknown")
    except (OSError, ValueError):
        return "unknown"


def load_manifest(project):
    p = os.path.join(project, STATE, "manifest.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def save_manifest(project, m):
    os.makedirs(os.path.join(project, STATE), exist_ok=True)
    readme = os.path.join(project, STATE, "README.md")
    if not os.path.exists(readme):
        open(readme, "w", encoding="utf-8").write(
            "# .agent-team\n\nWritten by the agent-team plugin. `base/` holds the template files as\n"
            "they were last installed or upgraded, so `/agent-team:upgrade` can merge new\n"
            "template versions with your changes. Commit this folder; do not edit it by hand.\n")
    with open(os.path.join(project, STATE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, sort_keys=True)
        f.write("\n")


def set_base(project, template, rel):
    dst = os.path.join(project, STATE, "base", rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(os.path.join(template, rel), dst)


def base_path(project, rel):
    return os.path.join(project, STATE, "base", rel)


def copy_file(template, project, rel):
    src, dst = os.path.join(template, rel), os.path.join(project, rel)
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    shutil.copy2(src, dst)


def load_profile(project, override=None):
    if override:
        return json.load(open(override, encoding="utf-8"))
    p = os.path.join(project, STATE, "config.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def render(raw, cfg):
    """(rendered template dir, profile module or None). The template's own profile
    engine renders it; a template without one is used as it is."""
    engine = os.path.join(raw, "scripts", "agentteam", "profile.py")
    if not os.path.exists(engine):
        return raw, None
    import importlib.util
    spec = importlib.util.spec_from_file_location("agentteam_profile", engine)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tempfile.mkdtemp(prefix="agent-team-template-")
    import atexit
    atexit.register(shutil.rmtree, out, True)
    mod.render_tree(raw, out, cfg)
    return out, mod


def classify(template, project, manifest, raw=None):
    """[(path, kind, note)] for every template file and every file the manifest knows."""
    known = set((manifest or {}).get("files", {}))
    rows = []
    for rel in template_files(template):
        new, proj, base = os.path.join(template, rel), os.path.join(project, rel), base_path(project, rel)
        has_proj, has_base = os.path.exists(proj), rel in known and os.path.exists(base)
        if rel in OWNED and has_proj:
            rows.append((rel, "owned", "yours after setup: never upgraded"))
        elif not has_proj and rel in known:
            rows.append((rel, "removed-by-you", "you deleted it; not re-added"))
        elif not has_proj:
            rows.append((rel, "add", "new in the template"))
        elif not has_base:
            same = sha(proj) == sha(new)
            rows.append((rel, "same" if same else "differs-no-base",
                         "identical" if same else "exists, no base to merge from: compare by hand"))
        else:
            b, p, n = sha(base), sha(proj), sha(new)
            if n == b:
                rows.append((rel, "unchanged", "template did not change it"))
            elif p == n:
                rows.append((rel, "same", "already equal to the new template"))
            elif p == b:
                rows.append((rel, "update", "you did not change it: safe update"))
            else:
                rows.append((rel, "merge", "both changed: three-way merge"))
    present = set(template_files(template))
    in_raw = set(template_files(raw)) if raw else present
    for rel in sorted(known - present):
        proj, base = os.path.join(project, rel), base_path(project, rel)
        if rel not in in_raw:
            rows.append((rel, "removed-upstream", "no longer in the template: kept, review it"))
        elif not os.path.exists(proj):
            rows.append((rel, "prune", "not in the profile, already gone"))
        elif os.path.exists(base) and sha(base) == sha(proj):
            rows.append((rel, "prune", "not in the profile and unchanged: removed"))
        else:
            rows.append((rel, "out-of-profile", "not in the profile but changed by you: kept, delete it if unneeded"))
    return rows


def summary(rows, show=("add", "update", "merge", "prune", "out-of-profile", "differs-no-base", "removed-upstream",
                        "removed-by-you")):
    by = {}
    for rel, kind, note in rows:
        by.setdefault(kind, []).append((rel, note))
    for kind in show:
        if kind in by:
            print(f"\n{kind} ({len(by[kind])}):")
            for rel, note in by[kind]:
                print(f"  {rel}  - {note}")
    quiet = sum(len(v) for k, v in by.items() if k not in show)
    print(f"\n{quiet} file(s) need nothing (unchanged, same or owned).")


def merge(template, project, rel):
    """Three-way merge into the project file. True when clean."""
    proj = os.path.join(project, rel)
    r = subprocess.run(["git", "merge-file", "-L", "project", "-L", "base", "-L", "template",
                        proj, base_path(project, rel), os.path.join(template, rel)],
                       capture_output=True, text=True)
    if r.returncode < 0 or r.returncode > 127:
        raise RuntimeError(f"git merge-file failed on {rel}: {r.stderr.strip()}")
    return r.returncode == 0


def cmd_install(a):
    if load_manifest(a.project) is not None:
        print("This project already has the agent-team template (.agent-team/manifest.json). "
              "Use the upgrade skill instead.", file=sys.stderr)
        return 2
    if a.profile and not a.dry_run:
        os.makedirs(os.path.join(a.project, STATE), exist_ok=True)
        dst = os.path.join(a.project, STATE, "config.json")
        if not os.path.exists(dst):
            shutil.copyfile(a.profile, dst)
    if a.engine:
        print("Profile: " + a.engine.describe(a.cfg))
    added, same, conflicts, kept = [], [], [], []
    for rel in template_files(a.template):
        proj = os.path.join(a.project, rel)
        if rel in OWNED and os.path.exists(proj):
            kept.append(rel)
        elif not os.path.exists(proj):
            added.append(rel)
        elif sha(proj) == sha(os.path.join(a.template, rel)):
            same.append(rel)
        else:
            conflicts.append(rel)
    print(f"{len(added)} file(s) to add, {len(same)} already identical, {len(conflicts)} existing and different"
          + (f", {len(kept)} of yours kept as they are ({', '.join(kept)})" if kept else "") + ".")
    if conflicts:
        print("\nExisting files that differ (NOT overwritten; merge them by hand, then `record` them):")
        for rel in conflicts:
            print(f"  {rel}")
    if a.dry_run:
        print("\n(dry run: nothing written)")
        return 0
    for rel in added:
        copy_file(a.template, a.project, rel)
    files = {}
    for rel in added + same:
        set_base(a.project, a.template, rel)
        files[rel] = sha(os.path.join(a.template, rel))
    save_manifest(a.project, {"plugin_version": plugin_version(a.raw), "installed": str(date.today()),
                              "upgraded": str(date.today()), "files": files,
                              "pending": sorted(conflicts)})
    print(f"\nInstalled: {len(added)} added. Manifest in {STATE}/manifest.json.")
    return 0


def cmd_status(a):
    m = load_manifest(a.project)
    rows = classify(a.template, a.project, m, a.raw)
    if a.json:
        json.dump({"installed_version": (m or {}).get("plugin_version"), "template_version": plugin_version(a.raw),
                   "profile": a.engine.describe(a.cfg) if a.engine else None,
                   "files": [{"path": r, "kind": k, "note": n} for r, k, n in rows]}, sys.stdout, indent=2)
        print()
        return 0
    print(f"Project template version: {(m or {}).get('plugin_version', 'none (no manifest)')}; "
          f"plugin template version: {plugin_version(a.raw)}.")
    if a.engine:
        print("Profile: " + a.engine.describe(a.cfg))
    if m is None:
        print("No manifest: files that differ from the template cannot be merged automatically; "
              "compare them by hand and `record` them.")
    summary(rows)
    return 0


def cmd_apply(a):
    m = load_manifest(a.project) or {"files": {}, "installed": str(date.today())}
    kinds = set(a.kinds.split(","))
    only = set(a.paths or [])
    rows = [r for r in classify(a.template, a.project, m, a.raw) if r[1] in kinds and (not only or r[0] in only)]
    conflicts = []
    for rel, kind, _ in rows:
        if a.dry_run:
            print(f"would {kind}: {rel}")
            continue
        if kind == "prune":
            for p in (os.path.join(a.project, rel), base_path(a.project, rel)):
                if os.path.exists(p):
                    os.remove(p)
                    d = os.path.dirname(p)
                    while d.startswith(a.project) and d != a.project and os.path.isdir(d) and not os.listdir(d):
                        os.rmdir(d)
                        d = os.path.dirname(d)
            m["files"].pop(rel, None)
            print(f"prune: {rel}")
            continue
        if kind in ("add", "update"):
            copy_file(a.template, a.project, rel)
        elif kind == "merge":
            if not merge(a.template, a.project, rel):
                conflicts.append(rel)
        set_base(a.project, a.template, rel)
        m["files"][rel] = sha(os.path.join(a.template, rel))
        print(f"{kind}: {rel}" + ("  (CONFLICT: resolve the markers)" if rel in conflicts else ""))
    if not a.dry_run:
        m["plugin_version"] = plugin_version(a.raw)
        m["upgraded"] = str(date.today())
        save_manifest(a.project, m)
    if conflicts:
        print("\nConflicts left between <<<<<<< project and >>>>>>> template markers in:")
        for rel in conflicts:
            print(f"  {rel}")
        return 1
    return 0


def cmd_record(a):
    m = load_manifest(a.project) or {"files": {}, "installed": str(date.today())}
    for rel in a.paths:
        if not os.path.exists(os.path.join(a.template, rel)):
            print(f"not a template file: {rel}", file=sys.stderr)
            return 2
        set_base(a.project, a.template, rel)
        m["files"][rel] = sha(os.path.join(a.template, rel))
        if rel in m.get("pending", []):
            m["pending"].remove(rel)
        print(f"recorded: {rel}")
    m["plugin_version"] = plugin_version(a.raw)
    save_manifest(a.project, m)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("install", "status", "apply", "record"):
        s = sub.add_parser(name)
        s.add_argument("--template", required=True)
        s.add_argument("--project", default=".")
        if name in ("install", "apply"):
            s.add_argument("--dry-run", action="store_true")
        if name == "install":
            s.add_argument("--profile", help="a config.json with the profile; copied to .agent-team/config.json")
        if name == "status":
            s.add_argument("--json", action="store_true")
        if name == "apply":
            s.add_argument("--kinds", default="add,update,merge,prune")
            s.add_argument("--paths", nargs="*")
        if name == "record":
            s.add_argument("--paths", nargs="+", required=True)
    a = ap.parse_args()
    a.template, a.project = os.path.abspath(a.template), os.path.abspath(a.project)
    if not os.path.isdir(a.template):
        print(f"template not found: {a.template}", file=sys.stderr)
        return 2
    a.raw = a.template
    try:
        a.cfg = load_profile(a.project, getattr(a, "profile", None))
        a.template, a.engine = render(a.raw, a.cfg)
    except (ValueError, OSError) as e:
        print(f"profile error: {e}", file=sys.stderr)
        return 2
    return {"install": cmd_install, "status": cmd_status, "apply": cmd_apply, "record": cmd_record}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
