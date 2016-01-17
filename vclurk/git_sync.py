import asyncio
from enum import Enum
from pathlib import Path
from .git_updater import fetch, update_branch
from .git.cmd import git
from .git.config import GitConfig

def read_refs_dir(p:Path):
    res = {}
    for file in p.iterdir():
        if file.is_file():
           with file.open('r') as f:
               res[file.name] = f.read().strip()

    return res

def get_current_branch(repo: Path):
    with (repo / '.git/HEAD').open() as f:
        head = f.read().strip()

    if head.startswith('ref: refs/heads/'):
        return head[len('ref: refs/heads/'):]
    return None

class CommitsRelationship(Enum):
    same = 1
    ancestor = 2
    descendant = 3
    divergent = 4

@asyncio.coroutine
def find_commit_relationship(a, b):
    """Describes the relationship of a to b.

    Returns a CommitsRelationship; e.g.CommitsRelationship.ancestor if a is
    an ancestor of b.
    """
    if a == b:
        return CommitsRelationship.same

    proc = yield from asyncio.create_subprocess_exec('git', 'merge-base', a, b,
                                stdout=asyncio.subprocess.PIPE)

    stdout, _ = yield from proc.communicate()
    merge_base = stdout.strip().decode('ascii')

    if merge_base == a:
        return CommitsRelationship.ancestor
    elif merge_base == b:
        return CommitsRelationship.descendant

    return CommitsRelationship.divergent


@asyncio.coroutine
def sync(repo, loop=None):
    repo = Path(repo)
    if loop is None:
        loop = asyncio.get_event_loop()

    cfg = GitConfig(str(repo))
    remote_names = set(r[0] for r in cfg.remotes())
    current_branch = get_current_branch(repo)

    remote_refs_before = {}
    remote_refs_after = {}

    remotes_to_fetch = ['origin', 'takluyver']
    for remote in remotes_to_fetch:
        if remote not in remote_names:
            continue

        refs_dir = repo / '.git/refs/remotes' / remote
        remote_refs_before[remote] = read_refs_dir(refs_dir)
        yield from fetch(repo, remote, loop=loop)
        remote_refs_after[remote] = read_refs_dir(refs_dir)

    local_refs = read_refs_dir(repo / '.git/refs/heads')

    branches_to_push = []
    branches_mismatched = []
    for branch_name, branch_cfg in cfg.branches():
        branch_remote = branch_cfg['remote']
        if branch_remote not in remotes_to_fetch:
            continue

        #remote_before = remote_refs_before[branch_remote][branch_name]
        remote_after  = remote_refs_after[branch_remote][branch_name]
        local = local_refs[branch_name]

        if remote_after == local:
            continue

        rel = yield from find_commit_relationship(local, remote_after)
        if rel is CommitsRelationship.ancestor:
            # fast forward
            if branch_name == current_branch:
                # TODO. This is a bit more fiddly
                continue
            branch_spec = 'remotes/{0}/{1}:{1}'.format(branch_remote, branch_name)
            yield from git(('fetch', '.', branch_spec), repo=repo)
            print('Updated branch', branch_name)

        elif rel is CommitsRelationship.descendant:
            branches_to_push.append(branch_name)
        else:
            branches_mismatched.append(branch_name)

def main(argv=None):
    repo = Path.cwd()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(sync(repo, loop))
    finally:
        loop.close()
