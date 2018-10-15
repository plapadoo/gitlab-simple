#!/usr/bin/env python

from typing import Dict, Any, Optional, List
from traceback import print_exc
from pathlib import Path
from textwrap import fill
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
from terminaltables import SingleTable
import consolemd


def retrieve_message() -> Optional[str]:
    initial_message = ""

    EDITOR = os.environ.get("EDITOR", "vim")

    print("invoking editor " + EDITOR)

    try:
        with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
            tf.write(initial_message.encode("utf-8"))
            tf.flush()
            run(EDITOR + " " + tf.name, shell=True, check=True)
            tf.seek(0)
            content: bytes = tf.read()
            result = content.decode("utf-8")
            if result == "":
                print("Abort, empty message")
                return None
            return result
    except:
        print("Abort, process error")
        print_exc()
        return None


parser = argparse.ArgumentParser(description="Simple gitlab interface")
parser.add_argument(
    "--new-snippet", action="store_true", help="create a new snippet (opens editor)"
)
parser.add_argument(
    "--file-type", type=str, help="file type (for snippets, for example)"
)
parser.add_argument(
    "--new-issue", action="store_true", help="create a new issue with a specific title"
)
parser.add_argument(
    "--edit-issue", action="store_true", help="edit an issue with an id"
)
parser.add_argument("--title", type=str, help="title of the item to be edited/inserted")
parser.add_argument("--version", action="store_true", help="display version info")
parser.add_argument("--iid", type=int, help="issue ID (other commands refer to that)")
parser.add_argument("--view-issue", action="store_true", help="view issue with id")
parser.add_argument("--comment-issue", type=str, help="add a short comment to an issue")
parser.add_argument(
    "--long-comment-issue",
    action="store_true",
    help="add a long comment to an issue (opens editor)",
)
parser.add_argument("--project", type=int, help="set the project id")
parser.add_argument(
    "--list-projects", action="store_true", help="list all accessible projects"
)
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


def load_config() -> Dict[str, Any]:
    config_path = Path(xdg_config_home) / "gitlab-simple" / "config.json"
    if not config_path.exists():
        raise Exception("config file “" + str(config_path) + "” not found")
    with config_path.open() as f:
        return json.load(f)  # type: ignore


def print_table(title: str, header: List[str], rows: List[List[str]]) -> None:
    table = SingleTable([header] + rows)
    max_width = table.column_max_width(1)
    overhead = table.column_max_width(0)
    if overhead < 0:
        for row in table.table_data:
            row[1] = fill(row[1], width=max_width)
    table.outer_border = False
    table.title = title
    print(table.table)


def find_user(project: Any, name: str) -> Optional[int]:
    return next((u.id for u in project.users.list() if u.name == name), None)


# pylint: disable=too-many-locals, too-many-branches, too-many-return-statements
def main(cliargs: Optional[List[str]] = None) -> int:
    if cliargs is None:
        cliargs = sys.argv[1:]

    args = parser.parse_args(cliargs)

    if args.version:
        print("gitlab-simple 1.2")
        return 0

    config = load_config()

    gl = gitlab.Gitlab(config["server"], private_token=config["token"])

    if args.list_projects:
        list_args = {"all": True}
        header = ["IID", "Name"]
        rows = [[str(p.id), p.name] for p in gl.projects.list(**list_args)]
        print_table(str(len(rows)) + " project(s)", header, rows)
        return 0

    if args.new_snippet:
        message = retrieve_message()
        if message is None:
            return 1
        title = args.title if args.title else "insert title here"
        file_type = args.file_type if args.file_type else "txt"
        snippet = gl.snippets.create(
            {"title": title, "file_name": "file." + file_type, "content": message}
        )
        print(snippet.web_url)
        return 0

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
        return 0

    if args.edit_issue:
        if not args.iid:
            print("please specify an issue id")
            return 1
        issue = project.issues.get(args.iid)
        if args.title:
            issue.title = args.title
        if args.editor:
            message = retrieve_message()
            if message is None:
                return 1
            issue.description = message
        if args.assign:
            user = find_user(project, args.assign)
            if user is None:
                print('user "' + args.assign + '" not found')
                return 1
            issue.assignee_id = user
        if args.labels:
            issue.labels = args.labels.split(",")
        issue.save()
        print("Edited issue")
        return 0

    if args.new_issue:
        if not args.title:
            print("please supply a title using --title")
            return 1
        d = {"title": args.title}
        if args.labels:
            d["labels"] = args.labels.split(",")
        if args.assign:
            user = find_user(project, args.assign)
            if user is None:
                print('user "' + args.assign + '" not found')
                return 1
            d["assignee_id"] = user
        if args.editor:
            message = retrieve_message()
            if message is None:
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

    if args.comment_issue:
        if not args.iid:
            print("please specify an issue id")
            return 1
        i = project.issues.get(args.iid)
        i.notes.create({"body": args.comment_issue})
        print("Comment created")

    if args.long_comment_issue:
        if not args.iid:
            print("please specify an issue id")
            return 1
        message = retrieve_message()
        if message is None:
            return 1
        i = project.issues.get(args.iid)
        i.notes.create({"body": message})
        print("Comment created")
        return 0

    if args.iid and args.view_issue is not None and args.view_issue:
        i = project.issues.get(args.iid)

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
        list_args = {"state": "opened", "all": True}
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
        print_table(str(len(rows)) + " issue(s)", header, rows)

    return 0


if __name__ == "__main__":
    main()
