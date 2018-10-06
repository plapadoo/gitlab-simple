#!/usr/bin/env python

from typing import Dict, Any, Optional, List
from traceback import print_exc
from pathlib import Path
import argparse
import json
from subprocess import run
import tempfile
import os
from datetime import datetime, timezone
import sys
import gitlab
from xdg.BaseDirectory import xdg_config_home
import dateutil.parser
import humanize
from terminaltables import AsciiTable
import consolemd


def retrieve_message() -> str:
    initial_message = ""

    EDITOR = os.environ.get("EDITOR", "vim")

    with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
        tf.write(initial_message.encode("utf-8"))
        tf.flush()
        run(EDITOR + " " + tf.name, shell=True, check=True)
        tf.seek(0)
        content: bytes = tf.read()
        return content.decode("utf-8")


parser = argparse.ArgumentParser(description="Simple gitlab interface")
parser.add_argument(
    "--new-issue", type=str, help="create a new issue with a specific title"
)
parser.add_argument("--version", action="store_true", help="display version info")
parser.add_argument("--issue", type=int, help="issue ID (other commands refer to that)")
parser.add_argument("--view-issue", action="store_true", help="view issue with id")
parser.add_argument("--comment-issue", type=str, help="add a short comment to an issue")
parser.add_argument(
    "--long-comment-issue",
    action="store_true",
    help="add a long comment to an issue (opens editor)",
)
parser.add_argument("--project", type=int, help="set the project id")
parser.add_argument("--list-issues", action="store_true", help="list project issues")
parser.add_argument(
    "--close-issues", type=str, help="close a comma-separated list of issue iids"
)
parser.add_argument(
    "--labels", type=str, help="comma-separated list of labels to use for the issue"
)
parser.add_argument(
    "--editor",
    action="store_true",
    help="invoke $EDITOR and ask for a long description",
)
parser.add_argument(
    "--latest-trace", action="store_true", help="get the latest job trace file"
)

parser.add_argument("--assign", type=str, help="assignee for the issue")

# pylint: disable=too-many-locals, too-many-branches
def main(cliargs: Optional[List[str]] = None) -> int:
    if cliargs is None:
        cliargs = sys.argv[1:]

    args = parser.parse_args(cliargs)

    if args.version:
        print("gitlab-simple 1.1")
        return 0

    config_path = Path(xdg_config_home) / "gitlab-simple" / "config.json"
    if not config_path.exists():
        raise Exception("config file “" + str(config_path) + "” not found")
    config: Dict[str, Any] = {}
    with config_path.open() as f:
        config = json.load(f)

    gl = gitlab.Gitlab(config["server"], private_token=config["token"])

    if args.project:
        print("using project from command line")
        project_id = args.project
    elif "GITLAB_SIMPLE_PROJECT" in os.environ:
        print("using project from envvar")
        project_id = os.environ["GITLAB_SIMPLE_PROJECT"]
    elif "project" in config:
        print("using project from config")
        project_id = gl.projects.get(config["project"])
    else:
        print(
            "Couldn't find a project in...\n\n"
            + "- GITLAB_SIMPLE_PROJECT environment variable\n"
            + "- the configuration file\n"
            + "- via --project on the command line\n\n"
            + "exiting..."
        )
        return 1

    project = gl.projects.get(project_id)

    if args.latest_trace is not None and args.latest_trace:
        jobs = [j for j in project.jobs.list() if j.status == "failed"]
        jobs.sort(key=lambda x: x.id, reverse=True)
        print(jobs[0].trace().decode("utf-8"))

    if args.new_issue is not None:
        d = {"title": args.new_issue}
        if args.labels is not None:
            d["labels"] = args.labels.split(",")
        if args.assign is not None:
            user = next(
                (u.id for u in project.users.list() if u.name == args.assign), None
            )
            d["assignee_id"] = user
        if args.editor is not None and args.editor:
            try:
                message = retrieve_message()
            except:
                print("Abort, process error")
                print_exc()
                return 1
            if message == "":
                print("Abort, empty message")
                return 1
            d["description"] = message
        created = project.issues.create(d)
        print("Created #" + str(created.iid))

    if args.close_issues is not None:
        issues = [a.strip() for a in args.close_issues.split(",")]

        for issue in (project.issues.get(issue) for issue in issues):
            issue.state_event = "close"
            issue.save()

        print("all closed")

    def humanize_time(t: datetime) -> str:
        return humanize.naturaldelta(
            datetime.now(timezone.utc) - dateutil.parser.parse(t)
        )

    if args.issue and args.comment_issue:
        i = project.issues.get(args.issue)
        i.notes.create({"body": args.comment_issue})
        print("Comment created")

    if args.issue and args.long_comment_issue:
        message = retrieve_message()
        i = project.issues.get(args.issue)
        i.notes.create({"body": message})
        print("Comment created")

    if args.issue and args.view_issue is not None and args.view_issue:
        i = project.issues.get(args.issue)

        result = "# *{}* [ {} ]\n".format(i.title, i.state)
        result += "## metadata\n"
        result += (
            "by "
            + i.author["username"]
            + ", 🕑"
            + humanize_time(i.created_at)
            + " ago\n"
        )
        if i.milestone is not None:
            result += "milestone: " + i.milestone["title"] + "\n"
        if i.assignees:
            result += "assigned to: " + i.assignees[0]["username"] + "\n"
        if i.labels:
            result += "labels: " + " ".join(i.labels) + "\n"
        result += "## description\n"
        result += i.description + "\n"
        comments = i.notes.list()
        if comments:
            result += "## comments\n"
            for c in comments:
                result += "### {} 🕑{} ago\n".format(
                    c.author["username"], humanize_time(c.created_at)
                )
                result += c.body + "\n"
        renderer = consolemd.Renderer(style_name="emacs")
        renderer.render(result)

    if args.list_issues is not None and args.list_issues:
        list_args = {"state": "opened", "per_page": "100"}
        if args.assign is not None:
            assignee_id: Optional[int] = next(
                (u.id for u in project.users.list() if u.name == args.assign), None
            )
            if assignee_id is not None:
                list_args["assignee_id"] = str(assignee_id)
        if args.labels is not None:
            list_args["labels"] = args.labels.split(",")
        header = ["IID", "Title", "Tags"]
        rows = [
            [
                str(issue.iid),
                issue.title,
                "" if not issue.labels else " ".join(issue.labels),
            ]
            for issue in project.issues.list(**list_args)
        ]
        print(AsciiTable([header] + rows).table)

    return 0


if __name__ == "__main__":
    main()
