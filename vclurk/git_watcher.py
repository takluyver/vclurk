import asyncio
import os.path
import pyinotify

from .git.config import GitConfig

def on_head_changed(event):
    print("HEAD changed")

class LocalBranchWatcher:
    def __init__(self, repo_path, git_config):
        self.repo_path = repo_path
        self.git_config = git_config

    def on_branch_changed(self, event):
        if (not event.name) or event.name.endswith('.lock'):
            return
        print("Local branch changed:", event.name)
        try:
            remote = self.git_config['branch', event.name, 'remote']
            print("Remote is:", remote)
        except KeyError:
            pass

    def setup_watch(self, watch_manager):
        watch_manager.add_watch(os.path.join(self.repo_path, '.git/refs/heads'),
                 mask=pyinotify.IN_MODIFY | pyinotify.IN_MOVED_TO,
                 proc_fun=self.on_branch_changed,
        )

def main():
    repo = '/home/takluyver/Code/ipython'
    loop = asyncio.get_event_loop()
    git_config = GitConfig(repo)
    wm = pyinotify.WatchManager()
    wm.add_watch(os.path.join(repo, '.git/config'), pyinotify.IN_MODIFY,
                 git_config.invalidate_cache)
    lbw = LocalBranchWatcher(repo, git_config=git_config)
    lbw.setup_watch(wm)
    #wm.add_watch(os.path.join(repo, '.git/HEAD'), pyinotify.IN_MODIFY, on_head_changed)

    notifier = pyinotify.AsyncioNotifier(wm, loop)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print()



if __name__ == '__main__':
    main()
