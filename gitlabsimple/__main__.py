#!/usr/bin/env python

from typing import Dict, Any, Optional
from traceback import print_exc
from pathlib import Path
import argparse
import json
from subprocess import run
import sys
import tempfile
import os
from datetime import datetime, timezone
import gitlab
from xdg.BaseDirectory import xdg_config_home
import dateutil.parser
import humanize
from termcolor import colored
from terminaltables import AsciiTable
import consolemd


def retrieve_message() -> str:
    initial_message = ""

    EDITOR = os.environ.get('EDITOR', 'vim')

    with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
        tf.write(initial_message.encode('utf-8'))
        tf.flush()
        run(
            EDITOR + " " + tf.name,
            shell=True,
            check=True,
        )
        tf.seek(0)
        content: bytes = tf.read()
        return content.decode('utf-8')


parser = argparse.ArgumentParser(description='Simple gitlab interface')
parser.add_argument(
    '--new-issue', type=str, help='create a new issue with a specific title')
parser.add_argument('--view-issue', type=int, help='ID of the issue to view')
parser.add_argument('--project', type=int, help='set the project id')
parser.add_argument(
    '--list-issues', action='store_true', help='list project issues')
parser.add_argument(
    '--close-issues',
    type=str,
    help='close a comma-separated list of issue iids')
parser.add_argument(
    '--labels',
    type=str,
    help='comma-separated list of labels to use for the issue')
parser.add_argument(
    '--editor',
    action='store_true',
    help='invoke $EDITOR and ask for a long description')
parser.add_argument(
    '--latest-trace',
    action='store_true',
    help='get the latest job trace file')

parser.add_argument('--assign', type=str, help='assignee for the issue')

args = parser.parse_args()

config_path = Path(xdg_config_home) / "gitlab-simple" / "config.json"
if not config_path.exists():
    raise Exception('config file “' + str(config_path) + "” not found")
config: Dict[str, Any] = {}
with config_path.open() as f:
    config = json.load(f)

gl = gitlab.Gitlab(
    config['server'],
    private_token=config['token'],
)

if "project" in config:
    project = gl.projects.get(config["project"])
elif "GITLAB_SIMPLE_PROJECT" in os.environ:
    project = os.environ["GITLAB_SIMPLE_PROJECT"]
else:
    if not args.project:
        print("Couldn't find a project in...\n\n" +
              "- GITLAB_SIMPLE_PROJECT environment variable\n" +
              "- the configuration file\n" +
              "- via --project on the command line\n\n" + "exiting...")
        sys.exit(1)
    else:
        project = args.project

if args.latest_trace is not None and args.latest_trace:
    jobs = [j for j in project.jobs.list() if j.status == 'failed']
    jobs.sort(key=lambda x: x.id, reverse=True)
    print(jobs[0].trace().decode('utf-8'))

if args.new_issue is not None:
    d = {
        'title': args.new_issue,
    }
    if args.labels is not None:
        d['labels'] = args.labels
    if args.assign is not None:
        user = next((u.id for u in project.users.list()
                     if u.name == args.assign), None)
        d['assignee_id'] = user
    if args.editor is not None and args.editor:
        try:
            message = retrieve_message()
        except:
            print("Abort, process error")
            print_exc()
            sys.exit(1)
        if message == '':
            print("Abort, empty message")
            sys.exit(1)
        else:
            d['description'] = message
    created = project.issues.create(d)
    print("Created #" + str(created.iid))

if args.close_issues is not None:
    issues = [a.strip() for a in args.close_issues.split(',')]

    for issue in (project.issues.get(issue) for issue in issues):
        issue.state_event = 'close'
        issue.save()

    print("all closed")


def humanize_time(t: datetime) -> str:
    return humanize.naturaldelta(
        datetime.now(timezone.utc) - dateutil.parser.parse(t))


if args.view_issue is not None and args.view_issue:
    i = project.issues.get(args.view_issue)

    result = "# *{}* [ {} ]\n".format(i.title, i.state)
    result += "## metadata\n"
    result += "by " + i.author['username'] + ", 🕑" + humanize_time(
        i.created_at) + " ago\n"
    if i.milestone is not None:
        result += "milestone: " + i.milestone['title'] + "\n"
    if i.assignees:
        result += "assigned to: " + i.assignees[0]['username'] + "\n"
    if i.labels:
        result += "labels: " + " ".join(i.labels) + "\n"
    result += "## description\n"
    result += i.description + "\n"
    comments = i.notes.list()
    if comments:
        result += "## comments\n"
        for c in comments:
            result += "### {} 🕑{} ago\n".format(c.author['username'],
                                                humanize_time(c.created_at))
            result += c.body + "\n"
    renderer = consolemd.Renderer(style_name='emacs')
    renderer.render(result)

if args.list_issues is not None and args.list_issues:
    list_args = {
        'state': 'opened',
        'per_page': '100',
    }
    if args.assign is not None:
        assignee_id: Optional[int] = next((u.id for u in project.users.list()
                                           if u.name == args.assign), None)
        if assignee_id is not None:
            list_args['assignee_id'] = str(assignee_id)
    if args.labels is not None:
        list_args['labels'] = args.labels.split(',')
    header = ["IID", "Title", "Tags"]
    rows = [[
        str(issue.iid),
        issue.title,
        '' if not issue.labels else ' '.join(issue.labels),
    ] for issue in project.issues.list(**list_args)]
    print(AsciiTable([header] + rows).table)
