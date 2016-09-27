# coding=utf-8
from __future__ import absolute_import, division, print_function

from click import command

from ..util.common_options import ansible_output_options
from ...util.playbook import playbook_path
from ...util.playbook_runner import PlaybookRunner

_short_help = 'Bootstrap a machine to be an Ansible controller node.'


@command(
    short_help=_short_help,
    help=_short_help + '''

In order for a machine to run Ansible playbooks, a set of requisite
dependencies need to be installed first. This command will install them
as well as a copy of this tool so that the node can be used to modify
itself.

\b
Examples:
  Bootstrap a machine
  $ oct bootstrap node
'''
)
@ansible_output_options
def node():
    """
    Bootstrap a machine to be an Ansible controller node.
    """
    PlaybookRunner().run(
        playbook_source=playbook_path('bootstrap/node')
    )