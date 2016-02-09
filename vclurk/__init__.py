"""vclurk"""

__version__ = "0.0.1"

from .subcmd import Commander, Subcommand

main = Commander('vclurk', [
    Subcommand('here', '.repos:add_main', 'Add the CWD to vclurk'),
    Subcommand('sync', '.git_sync:main', 'Sync this repository'),
], package='vclurk')
