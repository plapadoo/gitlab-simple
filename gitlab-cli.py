from typing import Dict, Any
import gitlab
import re
import subprocess
import argparse
from xdg.BaseDirectory import xdg_config_home

parser = argparse.ArgumentParser(description='Simple gitlab interface')
parser.add_argument(
    '--new-issue', type=str, help='create a new issue with a specific title')
parser.add_argument(
    '--close-issues',
    type=str,
    help='close a comma-separated list of issue iids')
parser.add_argument(
    '--labels',
    type=str,
    help='comma-separated list of labels to use for the issue')

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
    created = project.issues.create(d)
    print("Created #" + str(created.iid))

if args.close_issues is not None:
    issues = [a.strip() for a in args.close_issues.split(',')]

    for issue in (project.issues.get(issue) for issue in issues):
        issue.state_event = 'close'
        issue.save()

    print("all closed")
