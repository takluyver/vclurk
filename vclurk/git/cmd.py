import asyncio
from asyncio.subprocess import PIPE, STDOUT

capture_params = {
    'stdout': (PIPE, None),
    'stderr': (None, PIPE),
    'both'  : (PIPE, PIPE),
    'combine':(PIPE, STDOUT),
    'none'  : (None, None)
}

def git(args, repo, capture='stdout'):
    stdout, stderr = capture_params[capture]
    return asyncio.create_subprocess_exec(
        'git', *args,
        cwd=str(repo),
        stdout=stdout, stderr=stderr
    )
