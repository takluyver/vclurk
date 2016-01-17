import asyncio
import os
import re

cmd = asyncio.create_subprocess_exec

@asyncio.coroutine
def fetch(repo, remote='origin', loop=None):
    proc = yield from cmd('git', 'fetch', remote,
               stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
               loop=loop)

    branch_update_re = re.compile(r'\s+[0-9a-f]+\.\.[0-9a-f]+\s+\w+\s*\->\s+(\w+)/(\w+)')
    tracking_branches_updated = []
    while True:
        data = yield from proc.stdout.readline()
        if not data:
            break

        s = data.decode('ascii', 'replace')
        m = branch_update_re.match(s)
        if m:
            tracking_branches_updated.append(m.group(1, 2))

    yield from proc.wait()
    return tracking_branches_updated

@asyncio.coroutine
def update_branch(repo, branch_name, loop=None):
    # TODO: look up relevant remote in git config
    branch_spec = 'remotes/origin/{0}:{0}'.format(branch_name)
    # This doesn't work for the branch we're currently on
    proc = yield from cmd('git', 'fetch', '.', branch_spec, loop=loop)

    return (yield from proc.wait())


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    branches = loop.run_until_complete(fetch(os.getcwd()))
    print("Updated:")
    for b in branches:
        print("-", b)
    loop.close()
