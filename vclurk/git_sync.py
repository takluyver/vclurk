import asyncio
from collections import defaultdict
from enum import Enum
import logging
from pathlib import Path
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
def git_status(repo):
    proc = yield from git(('status', '--porcelain'), repo=repo, capture='stdout')
    b, _ = yield from proc.communicate()
    res = []
    for line in b.decode('utf-8').splitlines():
        res.append((line[0], line[1], line[3:]))
    return res

@asyncio.coroutine
def safe_to_pull(repo):
    status = yield from git_status(repo)
    # For our purposes, it's safe to update the current branch if no files
    # have been changed since the last commit, ignoring any untracked files.
    for stage_status, wd_status, filename in status:
        if (stage_status, wd_status) != ('?', '?'):
            return False
    return True

@asyncio.coroutine
def with_data(coro, data):
    res = yield from coro
    return res, data

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

    remotes_to_fetch = {'origin', 'takluyver'}.intersection(remote_names)
    for remote in remotes_to_fetch:
        remote_refs_before[remote] = read_refs_dir(repo / '.git/refs/remotes' / remote)
    print('Fetching:', remotes_to_fetch)
    p = yield from git(('fetch', '--multiple') + tuple(remotes_to_fetch), repo=repo, capture='none')
    yield from p.wait()
    for remote in remotes_to_fetch:
        remote_refs_after[remote] = read_refs_dir(repo / '.git/refs/remotes' / remote)

    local_refs = read_refs_dir(repo / '.git/refs/heads')

    finding_relationships = []
    for branch_name, branch_cfg in cfg.branches():
        branch_remote = branch_cfg['remote']
        if branch_remote not in remotes_to_fetch:
            continue

        #remote_before = remote_refs_before[branch_remote][branch_name]
        remote_after  = remote_refs_after[branch_remote][branch_name]
        local = local_refs[branch_name]

        if remote_after == local:
            continue  # Already in sync

        finding_relationships.append(with_data(find_commit_relationship(local, remote_after),
                                               (branch_name, branch_remote)))


    branches_to_push = []
    branches_conflicting = []
    for fut in asyncio.as_completed(finding_relationships):
        rel, (branch_name, branch_remote) = yield from fut
        if rel is CommitsRelationship.ancestor:
            # fast forward
            print('Can fast forward', branch_name)
            if branch_name == current_branch:
                if (yield from safe_to_pull(repo)):
                    p = yield from git(('reset', '{}/{}'.format(branch_remote, branch_name)), repo=repo)
                    yield from p.wait()
                    print('Updated {} (current branch)'.format(branch_name))
                else:
                    print("Can't update current branch while there are local changes.")
                    print("Use 'git pull' to update manually")
                continue
            branch_spec = 'remotes/{0}/{1}:{1}'.format(branch_remote, branch_name)
            p = yield from git(('fetch', '.', branch_spec), repo=repo)
            yield from p.wait()
            print('Updated branch', branch_name)
        elif rel is CommitsRelationship.descendant:
            branches_to_push.append((branch_name, branch_remote))
        elif rel is CommitsRelationship.divergent:
            branches_conflicting.append((branch_name, branch_remote))

    to_push_by_origin = defaultdict(list)
    for b, r in branches_to_push:
        to_push_by_origin[r].append(b)

    for remote, branches in to_push_by_origin.items():
        print("Pushing {} branches to {}".format(len(branches), remote))
        p = yield from git(['push', remote] + branches, repo)
        yield from p.wait()

    if branches_conflicting:
        print('Could not update these branches because of conflicts:')
        print(*branches_conflicting, sep=', ')

def main(argv=None):
    #logging.basicConfig(level=logging.DEBUG)
    repo = Path.cwd()
    loop = asyncio.get_event_loop()
    #loop.set_debug(True)
    try:
        loop.run_until_complete(sync(repo, loop))
    finally:
        loop.close()
