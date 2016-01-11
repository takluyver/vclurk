import os
from pathlib import Path

xdg_data_home = os.environ.get('XDG_DATA_DIR', '') or os.path.expanduser('~/.local/share')
vclurk_data = Path(xdg_data_home) / 'vclurk'
vclurk_repos = vclurk_data / 'repositories'

def ensure_dir_exists(path):
    try:
        path.mkdir(parents=True)
    except FileExistsError:
        pass

def add_repo(path):
    ensure_dir_exists(vclurk_repos)
    path = path.resolve()
    name = path.name
    n = 0
    link = vclurk_repos / name
    while link.exists():
        if link.resolve() == path:
            return link, True
        name = path.name + ('_%d' % n)
        link = vclurk_repos / name
        n += 1

    link.symlink_to(path)
    return link, False

_home = os.path.expanduser('~')
def compressuser(p):
    p2 = str(p)
    if p2.startswith(_home):
        return '~' + p2[len(_home):]
    return p2

def add_main(argv=None):
    d = Path.cwd()
    link, already = add_repo(d)
    if already:
        print("Already monitoring {}".format(compressuser(d)))
    else:
        print("{} added.".format(compressuser(d)))
