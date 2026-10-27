"""Redmine, REST API.

Configuration: "redmine": {"url": "https://redmine.example.com", "project": "identifier",
"tracker_id": null, "started_status": "In Progress", "hold_status": "On hold"}.
Authentication: REDMINE_API_KEY (My account > API access key; REST must be on).

Mapping: milestones are versions (Target version), sub-issues are subtasks,
dependencies are "blocks" relations. Redmine has no labels: a task counts as
started when its status is started_status, and on hold when it is hold_status.
"""
import os
import urllib.parse

from .. import core

REJECTED = {"rejected", "won't fix", "wontfix", "declined"}


class Adapter(core.Tracker):
    name = "redmine"
    html_markers = False

    def __init__(self, cfg):
        super().__init__(cfg)
        c = cfg.get("redmine") or {}
        if not c.get("url") or not c.get("project"):
            raise core.TrackerError('Redmine needs "redmine": {"url": ..., "project": ...} in .agent-team/config.json')
        if not os.environ.get("REDMINE_API_KEY"):
            raise core.TrackerError("Redmine needs REDMINE_API_KEY")
        self.base, self.project = c["url"].rstrip("/"), c["project"]
        self.tracker_id = c.get("tracker_id")
        self.started_status, self.hold_status = c.get("started_status", "In Progress"), c.get("hold_status", "On hold")
        self.auth = {"X-Redmine-API-Key": os.environ["REDMINE_API_KEY"]}
        self._statuses = self._me = None

    def req(self, method, path, body=None):
        return core.http_json(method, self.base + path, self.auth, body)

    def statuses(self):
        if self._statuses is None:
            self._statuses = {s["name"]: s for s in self.req("GET", "/issue_statuses.json")["issue_statuses"]}
        return self._statuses

    def _issue(self, i):
        st = (i.get("status") or {}).get("name", "")
        closed = bool(self.statuses().get(st, {}).get("is_closed"))
        issue = core.Issue(i["id"], f"#{i['id']}", i.get("subject"), i.get("description") or "",
                           open=not closed, done=closed and st.lower() not in REJECTED,
                           milestone=(i.get("fixed_version") or {}).get("name"),
                           parent=str(i["parent"]["id"]) if i.get("parent") else None,
                           url=f"{self.base}/issues/{i['id']}", author=(i.get("author") or {}).get("name"),
                           extra={"status": st, "relations": i.get("relations")})
        if st == self.started_status:
            issue.labels.append(f"agent:{core.role_of(issue) or 'unknown'}")
        if st == self.hold_status:
            issue.labels.append(core.HOLD)
        return issue

    def _list(self, **params):
        out, offset = [], 0
        while True:
            q = urllib.parse.urlencode(dict(params, status_id="*", limit=100, offset=offset))
            r = self.req("GET", f"/issues.json?{q}")
            out += r.get("issues", [])
            offset += len(r.get("issues", []))
            if not r.get("issues") or offset >= r.get("total_count", 0):
                return [self._issue(i) for i in out]

    def issues(self):
        return self._list(project_id=self.project)

    def get(self, ref):
        return self._issue(self.req("GET", f"/issues/{str(ref).lstrip('#')}.json?include=relations")["issue"])

    def milestones(self):
        rows = self.req("GET", f"/projects/{self.project}/versions.json").get("versions", [])
        return {core.code(v["name"]): (v["id"], v["name"]) for v in rows}

    def create_milestone(self, title, description):
        return self.req("POST", f"/projects/{self.project}/versions.json",
                        {"version": {"name": title, "description": description[:255]}})["version"]["id"]

    def create_issue(self, title, body, milestone=None, parent=None):
        i = {"project_id": self.project, "subject": title[:255], "description": body}
        if self.tracker_id:
            i["tracker_id"] = self.tracker_id
        if milestone:
            i["fixed_version_id"] = milestone
        if parent is not None:
            i["parent_issue_id"] = int(parent.ref)
        return self._issue(self.req("POST", "/issues.json", {"issue": i})["issue"])

    def _put(self, issue, fields):
        self.req("PUT", f"/issues/{issue.ref}.json", {"issue": fields})

    def set_milestone(self, issue, milestone_ref):
        self._put(issue, {"fixed_version_id": milestone_ref})

    def children(self, parent):
        return self._list(project_id=self.project, parent_id=parent.ref)

    def link_child(self, parent, child):
        self._put(child, {"parent_issue_id": int(parent.ref)})

    def unlink_child(self, parent, child):
        self._put(child, {"parent_issue_id": ""})

    def blockers(self, issue):
        rel = issue.extra.get("relations")
        if rel is None:
            rel = self.req("GET", f"/issues/{issue.ref}/relations.json").get("relations", [])
        return [str(r["issue_id"]) for r in rel
                if r.get("relation_type") == "blocks" and str(r.get("issue_to_id")) == issue.ref]

    def add_dependency(self, issue, blocker):
        try:
            self.req("POST", f"/issues/{blocker.ref}/relations.json",
                     {"relation": {"issue_to_id": int(issue.ref), "relation_type": "blocks"}})
            return True
        except core.TrackerError:
            return False

    def me(self):
        if self._me is None:
            self._me = self.req("GET", "/users/current.json")["user"]["id"]
        return self._me

    def comments(self, issue):
        me = self.me()
        j = self.req("GET", f"/issues/{issue.ref}.json?include=journals")["issue"].get("journals", [])
        return [core.Comment(x["notes"], (x.get("user") or {}).get("name", ""),
                             mine=(x.get("user") or {}).get("id") == me) for x in j if x.get("notes")]

    def comment(self, issue, body):
        self._put(issue, {"notes": body})

    def _status_id(self, name):
        s = self.statuses().get(name)
        if not s:
            raise core.TrackerError(f"Redmine status {name!r} not found: set started_status / hold_status")
        return s["id"]

    def add_label(self, issue, label):
        if label.startswith("agent:") and label != "agent:split":
            self._put(issue, {"status_id": self._status_id(self.started_status)})
        elif label == core.HOLD:
            self._put(issue, {"status_id": self._status_id(self.hold_status)})
        elif label != "agent:split":
            raise core.Unsupported("Redmine has no labels")

    def remove_label(self, issue, label):
        if label == "agent:split":
            return
        raise core.Unsupported("Redmine has no labels")

    def check(self):
        u = self.req("GET", "/users/current.json")["user"]
        missing = [s for s in (self.started_status, self.hold_status) if s not in self.statuses()]
        return [(True, f"Redmine {self.base} as {u.get('login')}"),
                (True, f"project {self.project}: {len(self.issues())} issues, {len(self.milestones())} versions readable"),
                (not missing, "statuses found" if not missing else f"statuses missing: {', '.join(missing)}")]
