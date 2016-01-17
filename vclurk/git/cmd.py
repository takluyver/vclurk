import asyncio

def git(args, repo):
    return asyncio.create_subprocess_exec(
        'git', *args,
        cwd=str(repo),
        stdout=asyncio.subprocess.PIPE
    )
