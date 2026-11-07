"""Jira (Cloud or Data Center), REST API v2.

Configuration: "jira": {"url": "https://you.atlassian.net", "project": "KEY",
"issue_type": "Task", "subtask_type": "Subtask"}.
Authentication: JIRA_EMAIL and JIRA_API_TOKEN (Cloud), or JIRA_PAT (Data Center).

Mapping: milestones are versions (Fix Version), sub-issues are sub-tasks,
dependencies are "Blocks" links, labels are labels. Jira has one level of
sub-tasks, so the tasks of a feature issue (key "...#feature") and the parts of
a sub-task are Tasks with a "Relates" link to their parent instead; children()
returns both kinds. Texts are converted from
Markdown to Jira wiki markup; markers are a plain last line "[agent-team] ...".
"""
import base64
import os
import re
import urllib.parse

from .. import core

WONT = {"won't do", "won't fix", "duplicate", "cannot reproduce", "declined", "rejected"}
FIELDS = "summary,description,status,resolution,labels,fixVersions,parent,issuelinks,issuetype,creator"


def md_to_jira(md):
    out, code = [], False
    lines = (md or "").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^```(\w*)\s*$", line)
        if m:
            out.append("{code}" if code else ("{code:%s}" % m.group(1) if m.group(1) else "{code}"))
            code = not code
            i += 1
            continue
        if code:
            out.append(line)
            i += 1
            continue
        if re.match(r"^\|.*\|\s*$", line) and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1]):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append("|| " + " || ".join(cells) + " ||")
            i += 2
            continue
        m = re.match(r"^(#{1,6}) (.*)$", line)
        if m:
            line = f"h{len(m.group(1))}. {m.group(2)}"
        line = re.sub(r"^(\s*)- ", lambda mm: "*" * (len(mm.group(1)) // 2 + 1) + " ", line)
        line = re.sub(r"`([^`]+)`", r"{{\1}}", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", line)
        out.append(line)
        i += 1
    return "\n".join(out)


class Adapter(core.Tracker):
    name = "jira"
    html_markers = False

    def __init__(self, cfg):
        super().__init__(cfg)
        c = cfg.get("jira") or {}
        if not c.get("url") or not c.get("project"):
            raise core.TrackerError('Jira needs "jira": {"url": ..., "project": ...} in .agent-team/config.json')
        self.base, self.project = c["url"].rstrip("/"), c["project"]
        self.issue_type, self.subtask_type = c.get("issue_type", "Task"), c.get("subtask_type", "Subtask")
        if os.environ.get("JIRA_PAT"):
            self.auth = {"Authorization": f"Bearer {os.environ['JIRA_PAT']}"}
        elif os.environ.get("JIRA_EMAIL") and os.environ.get("JIRA_API_TOKEN"):
            tok = base64.b64encode(f"{os.environ['JIRA_EMAIL']}:{os.environ['JIRA_API_TOKEN']}".encode()).decode()
            self.auth = {"Authorization": f"Basic {tok}"}
        else:
            raise core.TrackerError("Jira needs JIRA_EMAIL and JIRA_API_TOKEN (Cloud) or JIRA_PAT (Data Center)")
        self._pid = self._me = None

    def req(self, method, path, body=None):
        return core.http_json(method, self.base + path, self.auth, body)

    def format_body(self, markdown):
        return md_to_jira(markdown)

    def _issue(self, i):
        f = i.get("fields") or {}
        cat = (((f.get("status") or {}).get("statusCategory") or {}).get("key") or "")
        res = ((f.get("resolution") or {}).get("name") or "").lower()
        fv = f.get("fixVersions") or []
        return core.Issue(i["key"], i["key"], f.get("summary"), f.get("description") or "",
                          open=cat != "done", done=cat == "done" and res not in WONT,
                          labels=f.get("labels") or [], milestone=fv[0]["name"] if fv else None,
                          parent=(f.get("parent") or {}).get("key"), url=f"{self.base}/browse/{i['key']}",
                          author=(f.get("creator") or {}).get("displayName"),
                          extra={"links": f.get("issuelinks") or [],
                                 "subtask": bool((f.get("issuetype") or {}).get("subtask"))})

    def search(self, jql):
        out, token = [], None
        q = {"jql": jql, "fields": FIELDS, "maxResults": 100}
        try:
            while True:
                params = dict(q, **({"nextPageToken": token} if token else {}))
                r = self.req("GET", "/rest/api/2/search/jql?" + urllib.parse.urlencode(params))
                out += r.get("issues", [])
                token = r.get("nextPageToken")
                if not token or r.get("isLast"):
                    return [self._issue(i) for i in out]
        except core.TrackerError as e:
            if "HTTP 404" not in str(e):
                raise
        out, start = [], 0                         # Data Center: the classic endpoint
        while True:
            r = self.req("GET", "/rest/api/2/search?" + urllib.parse.urlencode(dict(q, startAt=start)))
            out += r.get("issues", [])
            start += len(r.get("issues", []))
            if not r.get("issues") or start >= r.get("total", 0):
                return [self._issue(i) for i in out]

    def issues(self):
        return self.search(f'project = "{self.project}" ORDER BY key ASC')

    def get(self, ref):
        return self._issue(self.req("GET", f"/rest/api/2/issue/{ref}?fields={FIELDS}"))

    def pid(self):
        if self._pid is None:
            self._pid = self.req("GET", f"/rest/api/2/project/{self.project}")["id"]
        return self._pid

    def milestones(self):
        rows = self.req("GET", f"/rest/api/2/project/{self.project}/versions") or []
        return {core.code(v["name"]): (v["id"], v["name"]) for v in rows}

    def create_milestone(self, title, description):
        return self.req("POST", "/rest/api/2/version",
                        {"name": title, "description": description, "projectId": int(self.pid())})["id"]

    def create_issue(self, title, body, milestone=None, parent=None):
        linked = parent is not None and (parent.extra.get("subtask") or (core.key_of(parent) or "").endswith("#feature"))
        sub = parent is not None and not linked
        fields = {"project": {"key": self.project}, "summary": title[:250], "description": md_to_jira(body),
                  "issuetype": {"name": self.subtask_type if sub else self.issue_type}}
        if milestone:
            fields["fixVersions"] = [{"id": str(milestone)}]
        if sub:
            fields["parent"] = {"key": parent.ref}
        r = self.req("POST", "/rest/api/2/issue", {"fields": fields})
        issue = core.Issue(r["key"], r["key"], title, body, url=f"{self.base}/browse/{r['key']}",
                           parent=parent.ref if sub else None, extra={"links": [], "subtask": sub})
        if linked:
            self.link_child(parent, issue)
        return issue

    def edit_issue(self, issue, title, body):
        self.req("PUT", f"/rest/api/2/issue/{issue.ref}", {"fields": {"summary": title[:250], "description": md_to_jira(body)}})

    def set_milestone(self, issue, milestone_ref):
        self.req("PUT", f"/rest/api/2/issue/{issue.ref}", {"update": {"fixVersions": [{"add": {"id": str(milestone_ref)}}]}})

    def children(self, parent):
        subs = self.search(f'parent = "{parent.ref}" ORDER BY key ASC')
        linked = [l["inwardIssue"]["key"] for l in self.get(parent.ref).extra.get("links", [])
                  if (l.get("type") or {}).get("name") == "Relates" and l.get("inwardIssue")]
        return subs + [self.get(k) for k in linked if k not in {s.ref for s in subs}]

    def link_child(self, parent, child):
        self.req("POST", "/rest/api/2/issueLink",
                 {"type": {"name": "Relates"}, "inwardIssue": {"key": child.ref}, "outwardIssue": {"key": parent.ref}})

    def blockers(self, issue):
        links = issue.extra.get("links")
        if links is None:
            links = self.get(issue.ref).extra.get("links", [])
        return [l["outwardIssue"]["key"] for l in links
                if (l.get("type") or {}).get("name") == "Blocks" and l.get("outwardIssue")]

    def add_dependency(self, issue, blocker):
        try:
            self.req("POST", "/rest/api/2/issueLink",
                     {"type": {"name": "Blocks"}, "inwardIssue": {"key": issue.ref}, "outwardIssue": {"key": blocker.ref}})
            return True
        except core.TrackerError:
            return False

    def me(self):
        if self._me is None:
            u = self.req("GET", "/rest/api/2/myself")
            self._me = u.get("accountId") or u.get("name")
        return self._me

    def comments(self, issue):
        me = self.me()
        rows = (self.req("GET", f"/rest/api/2/issue/{issue.ref}/comment?maxResults=100") or {}).get("comments", [])
        out = []
        for c in rows:
            a = c.get("author") or {}
            who = a.get("accountId") or a.get("name")
            out.append(core.Comment(c.get("body"), a.get("displayName", who), mine=who == me,
                                    bot=a.get("accountType") == "app"))
        return out

    def comment(self, issue, body):
        self.req("POST", f"/rest/api/2/issue/{issue.ref}/comment", {"body": md_to_jira(body)})

    def add_label(self, issue, label):
        self.req("PUT", f"/rest/api/2/issue/{issue.ref}", {"update": {"labels": [{"add": label}]}})

    def remove_label(self, issue, label):
        if label not in issue.labels:
            return
        self.req("PUT", f"/rest/api/2/issue/{issue.ref}", {"update": {"labels": [{"remove": label}]}})

    def check(self):
        me = self.req("GET", "/rest/api/2/myself")
        return [(True, f"Jira {self.base} as {me.get('displayName')}"),
                (True, f"project {self.project}: {len(self.issues())} issues, {len(self.milestones())} versions readable")]
