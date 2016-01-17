import asyncio
from asyncio.subprocess import PIPE, STDOUT
from subprocess import CalledProcessError

capture_params = {
    'stdout': (PIPE, None),
    'stderr': (None, PIPE),
    'both'  : (PIPE, PIPE),
    'combine':(PIPE, STDOUT),
    'none'  : (None, None)
}

class CompletedProcess:
    # This feels familiar
    def __init__(self, args, returncode, stdout, stderr):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def check_returncode(self):
        if self.returncode:
            raise CalledProcessError(self.returncode, self.args, self.stdout)

@asyncio.coroutine
def git(args, repo, capture='stdout'):
    stdout, stderr = capture_params[capture]
    proc = yield from asyncio.create_subprocess_exec(
        'git', *args,
        cwd=str(repo),
        stdout=stdout, stderr=stderr
    )
    stdout, stderr = yield from proc.communicate()
    return CompletedProcess(['git']+list(args), proc.returncode, stdout, stderr)
