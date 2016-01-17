import configparser
import os
import re

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

    def remotes(self):
        if not self.cache_up_to_date:
            self.read()

        remote_re = re.compile(r'remote "(.*)"')
        for k in self.config.sections():
            m = remote_re.match(k)
            if m:
                yield m.group(1), self.config[k]
