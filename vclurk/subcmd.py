from importlib import import_module
import sys

__version__ = '0.1'

class Subcommand:
    def __init__(self, name, entry_point, description=None):
        self.name = name
        self.entry_point = entry_point
        self.description = description

subcommands = [
    # User focussed
    ('install', '.urlinstall:main',
         'Download and install an application from a URL'),
    ('installtar', '.install:main',
         'Install a tarball that was already downloaded'),
    ('list', '.list:main',
         'List installed applications'),
    ('uninstall', '.uninstall:main',
         'Remove an installed application'),
    # Developer focussed
    ('verify', '.verify:main',
         'Check an application directory or tarball for problems'),
    ('pack', '.tarball:pack_main',
         'Pack an application directory into a tarball'),
    ('verify-index', '.verify_index:main',
         'Check a batis_index.json file for problems'),
]

class Commander:
    def __init__(self, description=None, subcmds=None, package=None):
        assert subcmds is not None
        #self.prog = prog
        self.description = description
        self.subcmds = subcmds
        self.package = package

    def __call__(self, argv=None):
        if argv is None:
            argv = sys.argv

        if len(argv) < 2:
            print('No subcommand specified')
            print('Available subcommands:', *(s.name for s in self.subcmds))
            return 2

        subcmd = argv[1]

        if subcmd in {'--help', '-h'}:
            print('Batis - install and distribute desktop applications')
            print('Subcommands:')
            for sc in self.subcmds:
                print('  {:<12} - {}'.format(sc.name, sc.description))
            return 0

        for sc in self.subcmds:
            if subcmd == sc.name:
                sub_main = self._load(sc.entry_point)
                return sub_main(argv[2:])

        print('Unknown subcommand: {!r}'.format(subcmd))
        print('Available subcommands:', *(s.name for s in self.subcmds))
        return 2

    def _load(self, entry_point):
        modname, func = entry_point.split(':')
        mod = import_module(modname, package=self.package)
        return getattr(mod, func)
