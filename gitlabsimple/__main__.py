#!/usr/bin/env python

from typing import Dict, Any
from traceback import print_exc
from pathlib import Path
import argparse
import json
from subprocess import run
import sys
import tempfile
import os
import gitlab
from xdg.BaseDirectory import xdg_config_home
from terminaltables import AsciiTable


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
        return tf.read().decode('utf-8')


parser = argparse.ArgumentParser(description='Simple gitlab interface')
parser.add_argument(
    '--new-issue', type=str, help='create a new issue with a specific title')
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

project = gl.projects.get(config["project"])

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

if args.list_issues is not None and args.list_issues:
    list_args = {
        'state': 'opened',
        'per_page': '100',
    }
    if args.assign is not None:
        list_args['assignee_id'] = next((u.id for u in project.users.list()
                                         if u.name == args.assign), None)
    if args.labels is not None:
        list_args['labels'] = args.labels.split(',')
    header = ["IID", "Title", "Tags"]
    rows = [[
        str(issue.iid), issue.title, ''
        if not issue.labels else ' '.join(issue.labels)
    ] for issue in project.issues.list(**list_args)]
    print(AsciiTable([header] + rows).table)
