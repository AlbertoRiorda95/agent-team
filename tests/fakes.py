"""In-memory fakes of the trackers' APIs, for tests/test_trackers.py.

They implement only what the adapters call, with the semantics the adapters rely
on. They do not prove that the real services behave the same way: for that, run
`python3 scripts/tracker.py check` against them.
"""
import json
import re
import urllib.parse


class P:
    def __init__(self, out="", rc=0, err=""):
        self.stdout, self.returncode, self.stderr = out, rc, err


# ------------------------------------------------------------------ GitHub (gh CLI)

class FakeGitHub:
    def __init__(self):
        self.issues, self.ms, self.subs, self.blocked, self.comments = {}, {}, {}, {}, {}
        self.n = 0

    def add(self, title, body="", milestone=None, labels=(), state="open", user="alberto"):
        self.n += 1
        self.issues[self.n] = {"number": self.n, "id": 1000 + self.n, "title": title, "body": body,
                               "state": state, "state_reason": "completed" if state == "closed" else None,
                               "labels": list(labels), "milestone": milestone, "user": user}
        return self.n

    def close(self, n, reason="completed"):
        self.issues[n]["state"], self.issues[n]["state_reason"] = "closed", reason

    def view(self, i, rest=False):
        ms = {"title": self.ms[i["milestone"]], "number": i["milestone"]} if i["milestone"] else None
        labels = [{"name": l} for l in i["labels"]]
        if rest:
            return {"number": i["number"], "id": i["id"], "title": i["title"], "body": i["body"], "state": i["state"],
                    "state_reason": i["state_reason"], "labels": labels, "milestone": ms,
                    "html_url": f"https://github.com/o/r/issues/{i['number']}", "user": {"login": i["user"]}}
        return {"number": i["number"], "title": i["title"], "body": i["body"], "state": i["state"].upper(),
                "stateReason": (i["state_reason"] or "").upper() or None, "labels": labels, "milestone": ms,
                "url": f"https://github.com/o/r/issues/{i['number']}", "author": {"login": i["user"]}}

    def sh(self, cmd, inp=None):
        a = cmd
        if a[:2] == ["gh", "auth"]:
            return P("ok")
        if a[:3] == ["gh", "issue", "list"]:
            return P(json.dumps([self.view(i) for i in self.issues.values()]))
        if a[:3] == ["gh", "issue", "comment"]:
            self.comments.setdefault(int(a[3]), []).append({"body": inp, "login": "alberto", "type": "User"})
            return P()
        if a[:3] == ["gh", "issue", "edit"]:
            i = self.issues[int(a[3])]
            if "--add-label" in a:
                i["labels"] = sorted(set(i["labels"] + [a[a.index("--add-label") + 1]]))
            if "--remove-label" in a:
                i["labels"] = [l for l in i["labels"] if l != a[a.index("--remove-label") + 1]]
            return P()
        if a[:2] != ["gh", "api"]:
            return P("", 1, f"unexpected {a}")
        args = a[2:]
        f = {x.split("=", 1)[0]: x.split("=", 1)[1] for k, x in zip(args, args[1:]) if k in ("-f", "-F")}
        method = args[args.index("-X") + 1] if "-X" in args else "GET"
        path = next(x for x in args if x.startswith("repos/") or x == "user")
        if path == "user":
            return P("alberto\n")
        m = re.match(r"repos/o/r/(.*)", path)
        rest = m.group(1).split("?")[0]
        if rest == "milestones":
            if method == "POST":
                k = len(self.ms) + 1
                self.ms[k] = f["title"]
                return P(json.dumps({"number": k}))
            return P("\n".join(json.dumps({"number": k, "title": t}) for k, t in self.ms.items()))
        if rest == "issues" and method == "POST":
            n = self.add(f["title"], f["body"], int(f["milestone"]) if "milestone" in f else None)
            return P(json.dumps({"number": n, "id": 1000 + n, "html_url": f"https://github.com/o/r/issues/{n}"}))
        m = re.match(r"issues/(\d+)(.*)", rest)
        n, sub = int(m.group(1)), m.group(2)
        if sub == "":
            if method == "PATCH":
                if "milestone" in f:
                    self.issues[n]["milestone"] = int(f["milestone"])
                for k in ("title", "body"):
                    if k in f:
                        self.issues[n][k] = f[k]
                return P("{}")
            if "--jq" in args and args[args.index("--jq") + 1] == ".id":
                return P(str(self.issues[n]["id"]))
            return P(json.dumps(self.view(self.issues[n], rest=True)))
        if sub == "/sub_issues":
            if method == "POST":
                self.subs.setdefault(n, []).append(int(f["sub_issue_id"]) - 1000)
                return P("{}")
            return P("\n".join(json.dumps(self.view(self.issues[c], rest=True)) for c in self.subs.get(n, [])))
        if sub == "/sub_issue" and method == "DELETE":
            self.subs[n].remove(int(f["sub_issue_id"]) - 1000)
            return P("{}")
        if sub == "/dependencies/blocked_by":
            if method == "POST":
                self.blocked.setdefault(n, []).append(int(f["issue_id"]) - 1000)
                return P("{}")
            return P("\n".join(str(b) for b in self.blocked.get(n, [])))
        if sub == "/comments":
            return P("\n".join(json.dumps(c) for c in self.comments.get(n, [])))
        return P("", 1, f"unexpected {a}")


# ------------------------------------------------------------------ Jira (REST v2)

class FakeJira:
    BASE = "https://jira.example.com"

    def __init__(self):
        self.issues, self.versions, self.comments, self.n = {}, [], {}, 0

    def add(self, summary, description="", parent=None, version=None):
        self.n += 1
        key = f"PROJ-{self.n}"
        self.issues[key] = {"key": key, "fields": {
            "summary": summary, "description": description, "status": {"statusCategory": {"key": "new"}},
            "resolution": None, "labels": [], "fixVersions": [version] if version else [],
            "parent": {"key": parent} if parent else None, "issuelinks": [], "creator": {"displayName": "Alberto"},
            "issuetype": {"name": "Subtask" if parent else "Task", "subtask": bool(parent)}}}
        return key

    def done(self, key, resolution="Done"):
        self.issues[key]["fields"]["status"] = {"statusCategory": {"key": "done"}}
        self.issues[key]["fields"]["resolution"] = {"name": resolution}

    def http(self, method, url, headers=None, body=None, timeout=30):
        assert headers and headers.get("Authorization"), "missing auth"
        u = urllib.parse.urlparse(url)
        path, q = u.path, dict(urllib.parse.parse_qsl(u.query))
        if path == "/rest/api/2/myself":
            return {"accountId": "me", "displayName": "Alberto"}
        if path == "/rest/api/2/search/jql":
            jql = q["jql"]
            m = re.search(r'parent = "([^"]+)"', jql)
            rows = [i for i in self.issues.values() if not m or (i["fields"]["parent"] or {}).get("key") == m.group(1)]
            return {"issues": rows, "isLast": True}
        if path == "/rest/api/2/project/PROJ":
            return {"id": "100"}
        if path == "/rest/api/2/project/PROJ/versions":
            return self.versions
        if path == "/rest/api/2/version" and method == "POST":
            assert body["projectId"] == 100
            v = {"id": str(len(self.versions) + 1), "name": body["name"]}
            self.versions.append(v)
            return v
        if path == "/rest/api/2/issue" and method == "POST":
            f = body["fields"]
            assert f["project"]["key"] == "PROJ"
            assert f["issuetype"]["name"] == ("Subtask" if "parent" in f else "Task")
            v = next((x for x in self.versions if x["id"] == f["fixVersions"][0]["id"]), None) if f.get("fixVersions") else None
            key = self.add(f["summary"], f["description"], (f.get("parent") or {}).get("key"), v)
            return {"key": key}
        if path == "/rest/api/2/issueLink":
            assert body["type"]["name"] in ("Blocks", "Relates")
            blocked, blocker = body["inwardIssue"]["key"], body["outwardIssue"]["key"]
            t = {"name": body["type"]["name"]}
            self.issues[blocked]["fields"]["issuelinks"].append({"type": t, "outwardIssue": {"key": blocker}})
            self.issues[blocker]["fields"]["issuelinks"].append({"type": t, "inwardIssue": {"key": blocked}})
            return None
        m = re.match(r"/rest/api/2/issue/([A-Z]+-\d+)(/comment)?$", path)
        if m:
            key, com = m.group(1), m.group(2)
            if com and method == "POST":
                self.comments.setdefault(key, []).append({"body": body["body"], "author": {"accountId": "me", "displayName": "Alberto"}})
                return {}
            if com:
                return {"comments": self.comments.get(key, [])}
            if method == "PUT":
                upd = body.get("update", {})
                f = self.issues[key]["fields"]
                f.update(body.get("fields", {}))
                for op in upd.get("fixVersions", []):
                    f["fixVersions"].append(next(v for v in self.versions if v["id"] == op["add"]["id"]))
                for op in upd.get("labels", []):
                    if "add" in op:
                        f["labels"].append(op["add"])
                    elif op["remove"] in f["labels"]:
                        f["labels"].remove(op["remove"])
                return None
            return self.issues[key]
        raise AssertionError(f"unexpected {method} {url}")


# ------------------------------------------------------------------ Redmine (REST)

class FakeRedmine:
    BASE = "https://redmine.example.com"
    STATUSES = [{"id": 1, "name": "New", "is_closed": False}, {"id": 2, "name": "In Progress", "is_closed": False},
                {"id": 3, "name": "Closed", "is_closed": True}, {"id": 4, "name": "Rejected", "is_closed": True},
                {"id": 5, "name": "On hold", "is_closed": False}]

    def __init__(self):
        self.issues, self.versions, self.relations, self.n = {}, [], [], 0

    def st(self, name):
        return next(s for s in self.STATUSES if s["name"] == name)

    def add(self, subject, description="", parent=None, version=None):
        self.n += 1
        self.issues[self.n] = {"id": self.n, "subject": subject, "description": description.replace("\n", "\r\n"),
                               "status": {"id": 1, "name": "New"}, "fixed_version": version,
                               "parent": {"id": parent} if parent else None, "author": {"name": "Alberto"}, "journals": []}
        return self.n

    def close(self, n, name="Closed"):
        s = self.st(name)
        self.issues[n]["status"] = {"id": s["id"], "name": s["name"]}

    def http(self, method, url, headers=None, body=None, timeout=30):
        assert headers.get("X-Redmine-API-Key")
        u = urllib.parse.urlparse(url)
        path, q = u.path, dict(urllib.parse.parse_qsl(u.query))
        if path == "/issue_statuses.json":
            return {"issue_statuses": self.STATUSES}
        if path == "/users/current.json":
            return {"user": {"id": 7, "login": "alberto"}}
        if path == "/projects/app/versions.json":
            if method == "POST":
                v = {"id": len(self.versions) + 1, "name": body["version"]["name"]}
                self.versions.append(v)
                return {"version": v}
            return {"versions": self.versions}
        if path == "/issues.json" and method == "GET":
            rows = [i for i in self.issues.values()
                    if "parent_id" not in q or (i["parent"] or {}).get("id") == int(q["parent_id"])]
            return {"issues": rows, "total_count": len(rows)}
        if path == "/issues.json" and method == "POST":
            i = body["issue"]
            v = next((x for x in self.versions if x["id"] == i.get("fixed_version_id")), None)
            n = self.add(i["subject"], i["description"], i.get("parent_issue_id"), v)
            return {"issue": self.issues[n]}
        m = re.match(r"/issues/(\d+)(/relations)?\.json$", path)
        if m:
            n, rel = int(m.group(1)), m.group(2)
            if rel and method == "POST":
                self.relations.append({"issue_id": n, "issue_to_id": body["relation"]["issue_to_id"],
                                       "relation_type": body["relation"]["relation_type"]})
                return {}
            if rel:
                return {"relations": [r for r in self.relations if n in (r["issue_id"], r["issue_to_id"])]}
            if method == "PUT":
                i, upd = self.issues[n], body["issue"]
                if "fixed_version_id" in upd:
                    i["fixed_version"] = next(v for v in self.versions if v["id"] == upd["fixed_version_id"])
                if "status_id" in upd:
                    s = next(s for s in self.STATUSES if s["id"] == upd["status_id"])
                    i["status"] = {"id": s["id"], "name": s["name"]}
                if "notes" in upd:
                    i["journals"].append({"notes": upd["notes"], "user": {"id": 7, "name": "Alberto"}})
                if "parent_issue_id" in upd:
                    i["parent"] = {"id": upd["parent_issue_id"]} if upd["parent_issue_id"] else None
                for k in ("subject", "description"):     # Redmine stores the text with \r\n, as the real one
                    if k in upd:
                        i[k] = upd[k].replace("\n", "\r\n") if k == "description" else upd[k]
                return None
            issue = dict(self.issues[n])
            if "relations" in q.get("include", ""):
                issue["relations"] = [r for r in self.relations if n in (r["issue_id"], r["issue_to_id"])]
            return {"issue": issue}
        raise AssertionError(f"unexpected {method} {url}")


# ------------------------------------------------------------------ Linear (GraphQL)

class FakeLinear:
    def __init__(self):
        self.issues, self.milestones, self.relations, self.labels, self.comments, self.n = {}, {}, [], {}, {}, 0

    def add(self, title, description="", parent=None, milestone=None):
        self.n += 1
        iid = f"uuid-{self.n}"
        self.issues[iid] = {"id": iid, "identifier": f"ENG-{self.n}", "title": title, "description": description,
                            "url": f"https://linear.app/x/issue/ENG-{self.n}", "state": {"type": "unstarted"},
                            "labels": [], "projectMilestone": milestone, "parent": parent, "creator": {"name": "Alberto"}}
        return iid

    def done(self, iid, kind="completed"):
        self.issues[iid]["state"] = {"type": kind}

    def view(self, i):
        d = dict(i)
        d["labels"] = {"nodes": [{"name": self.labels[l]} for l in i["labels"]]}
        d["projectMilestone"] = {"name": self.milestones[i["projectMilestone"]]} if i["projectMilestone"] else None
        d["parent"] = {"id": i["parent"]} if i["parent"] else None
        return d

    def find(self, ref):
        return self.issues.get(ref) or next(i for i in self.issues.values() if i["identifier"] == ref)

    def http(self, method, url, headers=None, body=None, timeout=30):
        assert headers.get("Authorization") == "lin_key"
        qy, v = body["query"], body["variables"]
        if "viewer" in qy:
            return {"data": {"viewer": {"id": "me", "name": "Alberto"}}}
        if "teams(" in qy:
            return {"data": {"teams": {"nodes": [{"id": "team-1"}]}}}
        if "projects(" in qy:
            return {"data": {"projects": {"nodes": [{"id": "proj-1"}]}}}
        if "issues(filter" in qy:
            return {"data": {"issues": {"nodes": [self.view(i) for i in self.issues.values()],
                                        "pageInfo": {"hasNextPage": False, "endCursor": None}}}}
        if "projectMilestones" in qy:
            return {"data": {"project": {"projectMilestones": {"nodes": [{"id": k, "name": n} for k, n in self.milestones.items()]}}}}
        if "projectMilestoneCreate" in qy:
            k = f"ms-{len(self.milestones) + 1}"
            self.milestones[k] = v["i"]["name"]
            return {"data": {"projectMilestoneCreate": {"projectMilestone": {"id": k}}}}
        if "issueCreate" in qy:
            i = v["i"]
            assert i["teamId"] == "team-1" and i["projectId"] == "proj-1"
            iid = self.add(i["title"], i["description"], i.get("parentId"), i.get("projectMilestoneId"))
            return {"data": {"issueCreate": {"issue": self.view(self.issues[iid])}}}
        if "issueUpdate" in qy:
            i, inp = self.find(v["id"]), v["i"]
            if "projectMilestoneId" in inp:
                i["projectMilestone"] = inp["projectMilestoneId"]
            if "parentId" in inp:
                i["parent"] = inp["parentId"]
            for k in ("title", "description"):
                if k in inp:
                    i[k] = inp[k]
            i["labels"] = sorted(set(i["labels"] + inp.get("addedLabelIds", [])) - set(inp.get("removedLabelIds", [])))
            return {"data": {"issueUpdate": {"success": True}}}
        if "issueRelationCreate" in qy:
            self.relations.append(v["i"])
            return {"data": {"issueRelationCreate": {"success": True}}}
        if "issueLabels(" in qy:
            hit = [k for k, n in self.labels.items() if n == v["n"]]
            return {"data": {"issueLabels": {"nodes": [{"id": k} for k in hit]}}}
        if "issueLabelCreate" in qy:
            k = f"lab-{len(self.labels) + 1}"
            self.labels[k] = v["i"]["name"]
            return {"data": {"issueLabelCreate": {"issueLabel": {"id": k}}}}
        if "commentCreate" in qy:
            self.comments.setdefault(v["i"]["issueId"], []).append(
                {"body": v["i"]["body"], "createdAt": str(len(self.comments)), "user": {"id": "me", "name": "Alberto"}})
            return {"data": {"commentCreate": {"success": True}}}
        if "comments(first" in qy:
            return {"data": {"issue": {"comments": {"nodes": self.comments.get(self.find(v["id"])["id"], [])}}}}
        if "children(first" in qy:
            pid = self.find(v["id"])["id"]
            return {"data": {"issue": {"children": {"nodes": [self.view(i) for i in self.issues.values() if i["parent"] == pid]}}}}
        if "inverseRelations" in qy:
            iid = self.find(v["id"])["id"]
            return {"data": {"issue": {"inverseRelations": {"nodes": [
                {"type": r["type"], "issue": {"id": r["issueId"]}} for r in self.relations if r["relatedIssueId"] == iid]}}}}
        if "issue(id:$id)" in qy:
            return {"data": {"issue": self.view(self.find(v["id"]))}}
        raise AssertionError(f"unexpected query {qy[:80]}")


# ------------------------------------------------------------------ GitLab (glab CLI)

class FakeGitLab:
    def __init__(self):
        self.issues, self.ms, self.links, self.notes, self.pipelines, self.n, self.lid = {}, {}, [], {}, [], 0, 0

    def add(self, title, description="", milestone=None):
        self.n += 1
        self.issues[self.n] = {"iid": self.n, "title": title, "description": description, "state": "opened",
                               "labels": [], "milestone": milestone, "web_url": f"https://gitlab/x/-/issues/{self.n}",
                               "author": {"username": "alberto"}}
        return self.n

    def close(self, iid):
        self.issues[iid]["state"] = "closed"

    def view(self, i):
        d = dict(i)
        d["milestone"] = {"id": i["milestone"], "title": self.ms[i["milestone"]]} if i["milestone"] else None
        return d

    def sh(self, cmd, inp=None):
        a = cmd
        if a[:2] == ["glab", "auth"]:
            return P("ok")
        assert a[:2] == ["glab", "api"], a
        args = a[2:]
        f = {x.split("=", 1)[0]: x.split("=", 1)[1] for k, x in zip(args, args[1:]) if k == "-f"}
        method = args[args.index("-X") + 1] if "-X" in args else "GET"
        path = next(x for x in args if x.startswith("projects/") or x == "user")
        if path == "user":
            return P(json.dumps({"id": 7, "username": "alberto"}))
        rest = path.split("projects/:fullpath", 1)[1].split("?")[0]
        if rest == "":
            return P(json.dumps({"id": 55, "default_branch": "main"}))
        if rest == "/issues":
            if method == "POST":
                n = self.add(f["title"], f["description"], int(f["milestone_id"]) if "milestone_id" in f else None)
                return P(json.dumps(self.view(self.issues[n])))
            page = int(dict(urllib.parse.parse_qsl(path.split("?", 1)[1])).get("page", 1))
            rows = [self.view(i) for i in self.issues.values()] if page == 1 else []
            return P(json.dumps(rows))
        if rest == "/milestones":
            if method == "POST":
                k = len(self.ms) + 1
                self.ms[k] = f["title"]
                return P(json.dumps({"id": k}))
            return P(json.dumps([{"id": k, "title": t} for k, t in self.ms.items()]))
        if rest == "/pipeline":
            self.pipelines.append(json.loads(inp))
            return P("{}")
        m = re.match(r"/issues/(\d+)(/links(?:/(\d+))?|/notes)?$", rest)
        n, sub, link_id = int(m.group(1)), m.group(2), m.group(3)
        if sub is None:
            i = self.issues[n]
            if method == "PUT":
                if "milestone_id" in f:
                    i["milestone"] = int(f["milestone_id"])
                for k in ("title", "description"):
                    if k in f:
                        i[k] = f[k]
                if "add_labels" in f:
                    i["labels"] = sorted(set(i["labels"] + [f["add_labels"]]))
                if "remove_labels" in f:
                    i["labels"] = [l for l in i["labels"] if l != f["remove_labels"]]
            return P(json.dumps(self.view(i)))
        if sub == "/notes":
            if method == "POST":
                self.notes.setdefault(n, []).append({"body": f["body"], "author": {"id": 7, "username": "alberto"}, "system": False})
                return P("{}")
            return P(json.dumps(self.notes.get(n, [])))
        if link_id and method == "DELETE":
            self.links = [l for l in self.links if l["id"] != int(link_id)]
            return P("{}")
        if method == "POST":
            self.lid += 1
            self.links.append({"id": self.lid, "from": n, "to": int(f["target_issue_iid"]),
                               "type": f.get("link_type", "relates_to")})
            return P("{}")
        out = []
        for l in self.links:
            if l["from"] == n:
                other, typ = l["to"], l["type"]
            elif l["to"] == n:
                other = l["from"]
                typ = {"is_blocked_by": "blocks", "blocks": "is_blocked_by"}.get(l["type"], l["type"])
            else:
                continue
            out.append(dict(self.view(self.issues[other]), issue_link_id=l["id"], link_type=typ))
        return P(json.dumps(out))
