"""GitLab, through the `glab` CLI (glab auth login, or GITLAB_TOKEN + GITLAB_HOST in CI).

Milestones are native milestones (free tier), children are linked issues
("relates to"), dependencies use "is blocked by" links where the plan allows them.
"""
import json
import os

from .. import core


class Adapter(core.Tracker):
    name = "gitlab"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.p = "projects/" + (os.environ.get("CI_PROJECT_ID") or ":fullpath")
        self._pid = self._me = self._branch = None

    def api(self, *args, inp=None):
        return json.loads(core.run(["glab", "api", *args], inp) or "null")

    def _issue(self, i):
        return core.Issue(i["iid"], f"#{i['iid']}", i.get("title"), i.get("description"),
                          open=i.get("state") == "opened", done=i.get("state") == "closed",
                          labels=i.get("labels", []), milestone=(i.get("milestone") or {}).get("title"),
                          url=i.get("web_url", ""), author=(i.get("author") or {}).get("username"),
                          extra={"link_id": i.get("issue_link_id"), "link_type": i.get("link_type")})

    def pid(self):
        if self._pid is None:
            info = self.api(self.p)
            self._pid, self._branch = info["id"], info.get("default_branch", "main")
        return self._pid

    def issues(self):
        out, page = [], 1
        while True:
            rows = self.api(f"{self.p}/issues?state=all&per_page=100&page={page}") or []
            out += [self._issue(i) for i in rows]
            if len(rows) < 100:
                return out
            page += 1

    def get(self, ref):
        return self._issue(self.api(f"{self.p}/issues/{str(ref).lstrip('#')}"))

    def milestones(self):
        rows, page = [], 1
        while True:
            ms = self.api(f"{self.p}/milestones?per_page=100&page={page}") or []
            rows += ms
            if len(ms) < 100:
                break
            page += 1
        return {core.code(m["title"]): (m["id"], m["title"]) for m in rows}

    def create_milestone(self, title, description):
        return self.api("-X", "POST", f"{self.p}/milestones", "-f", f"title={title}",
                        "-f", f"description={description}")["id"]

    def create_issue(self, title, body, milestone=None, parent=None):
        extra = ["-f", f"milestone_id={milestone}"] if milestone else []
        issue = self._issue(self.api("-X", "POST", f"{self.p}/issues", "-f", f"title={title}",
                                     "-f", f"description={body}", *extra))
        if parent is not None:
            self.link_child(parent, issue)
        return issue

    def set_milestone(self, issue, milestone_ref):
        self.api("-X", "PUT", f"{self.p}/issues/{issue.ref}", "-f", f"milestone_id={milestone_ref}")

    def _links(self, issue):
        return [self._issue(i) for i in self.api(f"{self.p}/issues/{issue.ref}/links") or []]

    def children(self, parent):
        return [i for i in self._links(parent) if i.extra.get("link_type") in (None, "relates_to")]

    def link_child(self, parent, child):
        self.api("-X", "POST", f"{self.p}/issues/{parent.ref}/links",
                 "-f", f"target_project_id={self.pid()}", "-f", f"target_issue_iid={child.ref}")

    def unlink_child(self, parent, child):
        for i in self._links(parent):
            if i.ref == child.ref and i.extra.get("link_id"):
                core.run(["glab", "api", "-X", "DELETE", f"{self.p}/issues/{parent.ref}/links/{i.extra['link_id']}"])

    def blockers(self, issue):
        try:
            return [i.ref for i in self._links(issue) if i.extra.get("link_type") == "is_blocked_by"]
        except core.TrackerError:
            return []

    def add_dependency(self, issue, blocker):
        p = core.sh(["glab", "api", "-X", "POST", f"{self.p}/issues/{issue.ref}/links",
                     "-f", f"target_project_id={self.pid()}", "-f", f"target_issue_iid={blocker.ref}",
                     "-f", "link_type=is_blocked_by"])
        return p.returncode == 0

    def me(self):
        if self._me is None:
            self._me = self.api("user")["id"]
        return self._me

    def comments(self, issue):
        me = self.me()
        notes = self.api(f"{self.p}/issues/{issue.ref}/notes?sort=asc&order_by=created_at&per_page=100") or []
        return [core.Comment(n["body"], n["author"]["username"], mine=n["author"]["id"] == me,
                             bot=bool(n["author"].get("bot")))
                for n in notes if not n.get("system")]

    def comment(self, issue, body):
        self.api("-X", "POST", f"{self.p}/issues/{issue.ref}/notes", "-f", f"body={body}")

    def add_label(self, issue, label):
        self.api("-X", "PUT", f"{self.p}/issues/{issue.ref}", "-f", f"add_labels={label}")

    def remove_label(self, issue, label):
        core.sh(["glab", "api", "-X", "PUT", f"{self.p}/issues/{issue.ref}", "-f", f"remove_labels={label}"])

    def run_pipeline(self, variables):
        self.pid()
        body = json.dumps({"ref": self._branch, "variables": [{"key": k, "value": v} for k, v in variables.items()]})
        core.run(["glab", "api", "-X", "POST", f"{self.p}/pipeline", "-H", "Content-Type: application/json",
                  "--input", "-"], body)

    def check(self):
        a = core.sh(["glab", "auth", "status"])
        return [(a.returncode == 0, "glab authenticated" if a.returncode == 0 else "glab not authenticated: glab auth login"),
                (True, f"project {self.pid()}: {len(self.issues())} issues, {len(self.milestones())} milestones readable")]
