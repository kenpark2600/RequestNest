"""Shared test fixtures: a fake UI and repo scaffolding."""

from __future__ import annotations

import subprocess

import pytest

from requestnest import config as cfg
from requestnest.context import AppContext


class FakeUI:
    """Records output and serves scripted answers — no terminal involved."""

    def __init__(self, prompts=None, selects=None, confirms=None):
        self.messages: dict[str, list[str]] = {
            "info": [],
            "success": [],
            "warn": [],
            "error": [],
            "detail": [],
        }
        self.diffs = []
        self.tables = []
        self.verbose = False
        self._prompts = list(prompts or [])
        self._selects = list(selects or [])
        self._confirms = list(confirms or [])

    def info(self, message):
        self.messages["info"].append(message)

    def success(self, message):
        self.messages["success"].append(message)

    def warn(self, message):
        self.messages["warn"].append(message)

    def error(self, message):
        self.messages["error"].append(message)

    def detail(self, message):
        self.messages["detail"].append(message)

    def confirm(self, question, *, default=False):
        return self._confirms.pop(0) if self._confirms else default

    def prompt(self, question, *, password=False, default=None):
        return self._prompts.pop(0) if self._prompts else (default or "")

    def select(self, title, options, *, preselect_all=True):
        if self._selects:
            return self._selects.pop(0)
        return [value for value, _ in options]

    def show_diff(self, diff):
        self.diffs.append(diff)

    def table(self, title, columns, rows):
        self.tables.append((title, columns, rows))

    # -- assertions helpers --------------------------------------------------
    def text(self, *kinds):
        kinds = kinds or tuple(self.messages)
        return " ".join(m for k in kinds for m in self.messages[k])


def make_app(tmp_path, ui=None, **kwargs):
    kwargs.setdefault("no_git", True)
    return AppContext(repo_root=tmp_path, ui=ui or FakeUI(), **kwargs)


def write_config(tmp_path, *, env_secrets=None):
    config = cfg.Config(
        collections=[cfg.Collection("orders", "collections/orders.json")],
        environments=[
            cfg.Environment("staging", "environments/staging.json", secrets=env_secrets or [])
        ],
    )
    cfg.save_config(tmp_path, config)
    return config


def write_state(tmp_path, *, with_uids=True):
    state = cfg.LocalState(api_key="PMAK-test")
    if with_uids:
        state.set_uid("collections", "orders", "cuid")
        state.set_uid("environments", "staging", "euid")
    cfg.save_state(tmp_path, state)
    return state


def git(path, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def fake_ui():
    return FakeUI()
