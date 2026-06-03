import subprocess

import pytest

from requestnest.gitops import GitError, GitRepo


def git(path, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-b", "main")
    # Persist a local identity so gitops' bare `git commit` works even on a
    # runner with no global git identity (e.g. GitHub Actions).
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "collections").mkdir()
    f = tmp_path / "collections" / "orders.json"
    f.write_text('{"a": 1}\n', encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-m", "init")
    return GitRepo(tmp_path)


def test_is_repo_and_branch(repo, tmp_path):
    assert repo.is_repo()
    assert repo.current_branch() == "main"
    assert not GitRepo(tmp_path / "nope").is_repo()


def test_file_at_head_and_dirty(repo):
    assert repo.file_at_head("collections/orders.json") == '{"a": 1}\n'
    assert repo.file_at_head("missing.json") is None
    assert not repo.is_dirty()
    (repo.root / "collections" / "orders.json").write_text('{"a": 2}\n', encoding="utf-8")
    assert repo.is_dirty()


def test_commit_returns_false_when_nothing_staged(repo):
    assert repo.commit("noop") is False


def test_add_and_commit(repo):
    (repo.root / "new.json").write_text("{}\n", encoding="utf-8")
    repo.add(["new.json"])
    assert repo.commit("add new") is True
    assert repo.file_at_head("new.json") == "{}\n"


def test_behind_count_and_upstream_changed_files(tmp_path):
    # Bare origin + two clones; clone B pushes, clone A detects it's behind.
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", "-b", "main", str(origin))

    work_a = tmp_path / "a"
    work_b = tmp_path / "b"
    git(tmp_path, "clone", str(origin), str(work_a))
    (work_a / "collections").mkdir()
    (work_a / "collections" / "orders.json").write_text('{"a": 1}\n', encoding="utf-8")
    git(work_a, "add", "-A")
    git(work_a, "commit", "-m", "init")
    git(work_a, "push", "origin", "main")

    git(tmp_path, "clone", str(origin), str(work_b))
    (work_b / "collections" / "orders.json").write_text('{"a": 2}\n', encoding="utf-8")
    git(work_b, "add", "-A")
    git(work_b, "commit", "-m", "upstream change")
    git(work_b, "push", "origin", "main")

    repo_a = GitRepo(work_a)
    repo_a.fetch("origin")
    assert repo_a.behind_count("origin", "main") == 1
    assert repo_a.upstream_changed_files("origin", "main") == ["collections/orders.json"]


def test_behind_count_zero_when_remote_ref_missing(repo):
    assert repo.behind_count("origin", "main") == 0
    assert repo.upstream_changed_files("origin", "main") == []


def test_run_raises_giterror_on_failure(repo):
    with pytest.raises(GitError):
        repo._run("rev-parse", "--verify", "definitely-not-a-ref")
