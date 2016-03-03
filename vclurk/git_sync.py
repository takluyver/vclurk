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
def find_commit_relationship(a, b, repo):
    """Describes the relationship of a to b.

    Returns a CommitsRelationship; e.g.CommitsRelationship.ancestor if a is
    an ancestor of b.
    """
    if a == b:
        return CommitsRelationship.same

    res = yield from git(('merge-base', a, b), repo, capture='stdout')
    merge_base = res.stdout.strip().decode('ascii')

    if merge_base == a:
        return CommitsRelationship.ancestor
    elif merge_base == b:
        return CommitsRelationship.descendant

    return CommitsRelationship.divergent

@asyncio.coroutine
def git_status(repo):
    cmd_res = yield from git(('status', '--porcelain'), repo=repo, capture='stdout')
    res = []
    for line in cmd_res.stdout.decode('utf-8').splitlines():
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
    yield from git(('fetch', '--multiple') + tuple(remotes_to_fetch), repo=repo, capture='none')
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

        finding_relationships.append(with_data(
                find_commit_relationship(local, remote_after, repo),
                (branch_name, branch_remote)
        ))


    branches_to_push = []
    branches_conflicting = []
    branches_updated = []
    for fut in asyncio.as_completed(finding_relationships):
        rel, (branch_name, branch_remote) = yield from fut
        if rel is CommitsRelationship.ancestor:
            # fast forward
            print('Can fast forward', branch_name)
            if branch_name == current_branch:
                if (yield from safe_to_pull(repo)):
                    yield from git(('reset', '--keep', '{}/{}'.format(branch_remote, branch_name)), repo=repo)
                    print('Updated {} (current branch)'.format(branch_name))
                    branches_updated.append(branch_name)
                else:
                    print("Can't update current branch while there are local changes.")
                    print("Use 'git pull' to update manually")
                continue
            branch_spec = 'remotes/{0}/{1}:{1}'.format(branch_remote, branch_name)
            yield from git(('fetch', '.', branch_spec), repo=repo)
            print('Updated branch', branch_name)
            branches_updated.append(branch_name)
        elif rel is CommitsRelationship.descendant:
            branches_to_push.append((branch_name, branch_remote))
        elif rel is CommitsRelationship.divergent:
            branches_conflicting.append((branch_name, branch_remote))

    # If the branch we're on was merged into master, switch to master
    if ('master' in local_refs) and current_branch != 'master':
        master_remote = cfg['branch', 'master', 'remote']
        master_commit = remote_refs_after[master_remote]['master']
        if current_branch in branches_updated:
            current_remote = cfg['branch', current_branch, 'remote']
            current_commit = remote_refs_after[current_remote][current_branch]
        else:
            current_commit = local_refs[current_branch]
        rel = yield from find_commit_relationship(current_commit, master_commit, repo)
        if rel is CommitsRelationship.ancestor:
            if (yield from safe_to_pull(repo)):
                yield from git(('checkout', 'master'), repo)
            else:
                print('Branch merged to master, but there are uncommitted changes.')
                print('To switch manually, run:')
                print('  git checkout master')

    to_push_by_origin = defaultdict(list)
    for b, r in branches_to_push:
        to_push_by_origin[r].append(b)

    for remote, branches in to_push_by_origin.items():
        print("Pushing {} branches to {}".format(len(branches), remote))
        yield from git(['push', remote] + branches, repo)

    if branches_conflicting:
        print('Could not update these branches because of conflicts:')
        print(*branches_conflicting, sep=', ')
    elif not (to_push_by_origin or branches_updated):
        print("All branches already up to date. :-)")

def main(argv=None):
    #logging.basicConfig(level=logging.DEBUG)
    repo = Path.cwd()
    loop = asyncio.get_event_loop()
    #loop.set_debug(True)
    try:
        loop.run_until_complete(sync(repo, loop))
    finally:
        loop.close()
