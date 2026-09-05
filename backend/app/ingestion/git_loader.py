from git import Repo

class GitLoader:

    def load(self, repository_path: str):
        repo = Repo(repository_path)

        commits = []

        for commit in repo.iter_commits():
            commits.append({
                "hash": commit.hexsha,
                "author": commit.author.name,
                "message": commit.message.strip(),
                "branch": self._get_branch(commit),
                "timestamp": commit.committed_datetime,
            })
            return commits

        def _get_branch(self, commit):
            branches = []

            for branch in commit.repo.branches:
                if branch.commit.hexsha == commit.hexsha:
                    branches.append(branch.name)

            return branches[0] if branches else "unknown"        