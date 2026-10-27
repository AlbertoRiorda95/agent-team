"""Linear, GraphQL API.

Configuration: "linear": {"team": "ENG", "project": "Project name or id"}.
Authentication: LINEAR_API_KEY (a personal API key).

Mapping: milestones are project milestones (they need "project"), sub-issues are
sub-issues, dependencies are "blocks" relations, labels are team labels (created
when missing). Issues are identified by their identifier, such as ENG-12.
"""
import os

from .. import core

URL = "https://api.linear.app/graphql"
ISSUE = ("id identifier title description url state { type } labels { nodes { name } } "
         "projectMilestone { name } parent { id } creator { name }")


class Adapter(core.Tracker):
    name = "linear"
    html_markers = False

    def __init__(self, cfg):
        super().__init__(cfg)
        c = cfg.get("linear") or {}
        if not c.get("team"):
            raise core.TrackerError('Linear needs "linear": {"team": "KEY"} in .agent-team/config.json')
        if not os.environ.get("LINEAR_API_KEY"):
            raise core.TrackerError("Linear needs LINEAR_API_KEY")
        self.auth = {"Authorization": os.environ["LINEAR_API_KEY"]}
        self.team_key, self.project_name = c["team"], c.get("project")
        self._team = self._project = self._me = None
        self._labels = {}

    def q(self, query, **variables):
        r = core.http_json("POST", URL, self.auth, {"query": query, "variables": variables})
        if r.get("errors"):
            raise core.TrackerError("Linear: " + "; ".join(e.get("message", "") for e in r["errors"]))
        return r["data"]

    def team(self):
        if self._team is None:
            n = self.q("query($k:String!){teams(filter:{key:{eq:$k}}){nodes{id}}}", k=self.team_key)["teams"]["nodes"]
            if not n:
                raise core.TrackerError(f"Linear team {self.team_key} not found")
            self._team = n[0]["id"]
        return self._team

    def project(self):
        if self._project is None and self.project_name:
            n = self.q("query($n:String!){projects(filter:{or:[{name:{eq:$n}},{id:{eq:$n}}]}){nodes{id}}}",
                       n=self.project_name)["projects"]["nodes"]
            if not n:
                raise core.TrackerError(f"Linear project {self.project_name} not found")
            self._project = n[0]["id"]
        return self._project

    def _issue(self, i):
        st = (i.get("state") or {}).get("type")
        return core.Issue(i["id"], i["identifier"], i.get("title"), i.get("description") or "",
                          open=st not in ("completed", "canceled"), done=st == "completed",
                          labels=[l["name"] for l in (i.get("labels") or {}).get("nodes", [])],
                          milestone=(i.get("projectMilestone") or {}).get("name"),
                          parent=(i.get("parent") or {}).get("id"), url=i.get("url", ""),
                          author=(i.get("creator") or {}).get("name"))

    def issues(self):
        flt = {"team": {"id": {"eq": self.team()}}}
        if self.project():
            flt["project"] = {"id": {"eq": self.project()}}
        out, after = [], None
        while True:
            d = self.q("query($f:IssueFilter,$a:String){issues(filter:$f,first:100,after:$a)"
                       "{nodes{" + ISSUE + "} pageInfo{hasNextPage endCursor}}}", f=flt, a=after)["issues"]
            out += [self._issue(i) for i in d["nodes"]]
            if not d["pageInfo"]["hasNextPage"]:
                return out
            after = d["pageInfo"]["endCursor"]

    def get(self, ref):
        return self._issue(self.q("query($id:String!){issue(id:$id){" + ISSUE + "}}", id=str(ref))["issue"])

    def milestones(self):
        if not self.project():
            raise core.Unsupported('milestones need "project" in the linear configuration')
        n = self.q("query($id:String!){project(id:$id){projectMilestones{nodes{id name}}}}",
                   id=self.project())["project"]["projectMilestones"]["nodes"]
        return {core.code(m["name"]): (m["id"], m["name"]) for m in n}

    def create_milestone(self, title, description):
        if not self.project():
            raise core.Unsupported('milestones need "project" in the linear configuration')
        r = self.q("mutation($i:ProjectMilestoneCreateInput!){projectMilestoneCreate(input:$i){projectMilestone{id}}}",
                   i={"projectId": self.project(), "name": title, "description": description})
        return r["projectMilestoneCreate"]["projectMilestone"]["id"]

    def create_issue(self, title, body, milestone=None, parent=None):
        inp = {"teamId": self.team(), "title": title, "description": body}
        if self.project():
            inp["projectId"] = self.project()
        if milestone:
            inp["projectMilestoneId"] = milestone
        if parent is not None:
            inp["parentId"] = parent.ref
        r = self.q("mutation($i:IssueCreateInput!){issueCreate(input:$i){issue{" + ISSUE + "}}}", i=inp)
        return self._issue(r["issueCreate"]["issue"])

    def _update(self, issue, inp):
        self.q("mutation($id:String!,$i:IssueUpdateInput!){issueUpdate(id:$id,input:$i){success}}", id=issue.ref, i=inp)

    def set_milestone(self, issue, milestone_ref):
        self._update(issue, {"projectMilestoneId": milestone_ref})

    def children(self, parent):
        n = self.q("query($id:String!){issue(id:$id){children(first:100){nodes{" + ISSUE + "}}}}",
                   id=parent.ref)["issue"]["children"]["nodes"]
        return [self._issue(i) for i in n]

    def link_child(self, parent, child):
        self._update(child, {"parentId": parent.ref})

    def unlink_child(self, parent, child):
        self._update(child, {"parentId": None})

    def blockers(self, issue):
        n = self.q("query($id:String!){issue(id:$id){inverseRelations{nodes{type issue{id}}}}}",
                   id=issue.ref)["issue"]["inverseRelations"]["nodes"]
        return [r["issue"]["id"] for r in n if r["type"] == "blocks"]

    def add_dependency(self, issue, blocker):
        try:
            self.q("mutation($i:IssueRelationCreateInput!){issueRelationCreate(input:$i){success}}",
                   i={"issueId": blocker.ref, "relatedIssueId": issue.ref, "type": "blocks"})
            return True
        except core.TrackerError:
            return False

    def me(self):
        if self._me is None:
            self._me = self.q("query{viewer{id}}")["viewer"]["id"]
        return self._me

    def comments(self, issue):
        n = self.q("query($id:String!){issue(id:$id){comments(first:100){nodes{body createdAt user{id name}}}}}",
                   id=issue.ref)["issue"]["comments"]["nodes"]
        me = self.me()
        n.sort(key=lambda c: c.get("createdAt") or "")
        return [core.Comment(c["body"], (c.get("user") or {}).get("name", "bot"),
                             mine=(c.get("user") or {}).get("id") == me, bot=c.get("user") is None) for c in n]

    def comment(self, issue, body):
        self.q("mutation($i:CommentCreateInput!){commentCreate(input:$i){success}}", i={"issueId": issue.ref, "body": body})

    def _label(self, name):
        if name not in self._labels:
            n = self.q("query($n:String!,$t:ID!){issueLabels(filter:{name:{eq:$n},team:{id:{eq:$t}}}){nodes{id}}}",
                       n=name, t=self.team())["issueLabels"]["nodes"]
            if n:
                self._labels[name] = n[0]["id"]
            else:
                r = self.q("mutation($i:IssueLabelCreateInput!){issueLabelCreate(input:$i){issueLabel{id}}}",
                           i={"name": name, "teamId": self.team()})
                self._labels[name] = r["issueLabelCreate"]["issueLabel"]["id"]
        return self._labels[name]

    def add_label(self, issue, label):
        self._update(issue, {"addedLabelIds": [self._label(label)]})

    def remove_label(self, issue, label):
        if label in issue.labels:
            self._update(issue, {"removedLabelIds": [self._label(label)]})

    def check(self):
        v = self.q("query{viewer{name}}")["viewer"]
        out = [(True, f"Linear as {v['name']}, team {self.team_key}")]
        out.append((True, f"{len(self.issues())} issues readable"))
        out.append((bool(self.project()), f"project {self.project_name}" if self.project()
                    else 'no "project": milestones are not available'))
        return out
