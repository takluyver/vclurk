import asyncio
import configparser
import os.path
import pyinotify
import re

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


class GitConfig:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.cache_up_to_date = False
        self.config = configparser.ConfigParser()

    @property
    def config_path(self):
        return os.path.join(self.repo_path, '.git', 'config')

    def invalidate_cache(self):
        self.cache_up_to_date = False

    def read(self):
        config = configparser.ConfigParser()
        config.read(self.config_path)
        self.config = config
        self.cache_up_to_date = True

    def __getitem__(self, item):
        if not self.cache_up_to_date:
            self.read()

        if isinstance(item, tuple):
            if len(item) == 3:
                return self.config['%s "%s"' % (item[0], item[1])][item[2]]
            elif len(item) == 2:
                return self.config[item[0]][item[1]]

        return self.config[item]

    def branches(self):
        if not self.cache_up_to_date:
            self.read()

        branch_re = re.compile(r'branch "(.*)"')
        for k in self.config.sections():
            m = branch_re.match(k)
            if m:
                yield m.group(1), self.config[k]


if __name__ == '__main__':
    main()
