import json

import httpx
import pytest
import respx

from conftest import FakeUI, make_app, write_config, write_state
from requestnest import config as cfg
from requestnest import sync
from requestnest.postman import BASE_URL

BASE = BASE_URL


def collection_response(item=None):
    return {
        "collection": {
            "info": {"name": "Orders", "_postman_id": "vol"},
            "item": item
            or [{"id": "1", "name": "list", "request": {"method": "GET", "url": "https://x"}}],
        }
    }


def environment_response(values=None):
    return {
        "environment": {
            "id": "evol",
            "name": "staging",
            "values": values
            or [
                {"key": "base_url", "value": "https://x", "type": "default"},
                {"key": "api_token", "value": "SUPER-SECRET", "type": "secret"},
            ],
        }
    }


# --------------------------------------------------------------------------- #
# push
# --------------------------------------------------------------------------- #


@respx.mock
def test_push_sanitizes_secrets_and_writes_files(tmp_path):
    write_config(tmp_path)
    write_state(tmp_path)
    respx.get(f"{BASE}/collections/cuid").mock(
        return_value=httpx.Response(200, json=collection_response())
    )
    respx.get(f"{BASE}/environments/euid").mock(
        return_value=httpx.Response(200, json=environment_response())
    )

    app = make_app(tmp_path)
    sync.push(app, names=())

    env_text = (tmp_path / "environments/staging.json").read_text(encoding="utf-8")
    assert "SUPER-SECRET" not in env_text  # secret never committed
    env = json.loads(env_text)
    token = next(v for v in env["values"] if v["key"] == "api_token")
    assert token["value"] == "{{api_token}}"

    # Volatile ids stripped from the committed collection.
    coll_text = (tmp_path / "collections/orders.json").read_text(encoding="utf-8")
    assert "_postman_id" not in coll_text
    assert '"id"' not in coll_text

    # Captured secret stored locally; example scaffold written.
    assert cfg.load_secrets(tmp_path)["staging"]["api_token"] == "SUPER-SECRET"
    example = (tmp_path / cfg.SECRETS_EXAMPLE_FILENAME).read_text(encoding="utf-8")
    assert "api_token" in example
    assert "SUPER-SECRET" not in example


@respx.mock
def test_push_aborts_on_unmarked_secret(tmp_path):
    write_config(tmp_path)
    write_state(tmp_path)
    leaky = collection_response(
        item=[
            {
                "id": "1",
                "name": "call",
                "request": {
                    "method": "GET",
                    "url": "https://x",
                    "header": [{"key": "Authorization", "value": "AKIAIOSFODNN7EXAMPLE"}],
                },
            }
        ]
    )
    respx.get(f"{BASE}/collections/cuid").mock(return_value=httpx.Response(200, json=leaky))

    app = make_app(tmp_path)
    with pytest.raises(sync.SyncError, match="unmarked secret"):
        sync.push(app, names=("orders",))
    assert not (tmp_path / "collections/orders.json").exists()  # nothing written


@respx.mock
def test_push_dry_run_writes_nothing(tmp_path):
    write_config(tmp_path)
    write_state(tmp_path)
    respx.get(f"{BASE}/collections/cuid").mock(
        return_value=httpx.Response(200, json=collection_response())
    )
    respx.get(f"{BASE}/environments/euid").mock(
        return_value=httpx.Response(200, json=environment_response())
    )

    ui = FakeUI()
    app = make_app(tmp_path, ui=ui, dry_run=True)
    sync.push(app, names=())

    assert not (tmp_path / "collections/orders.json").exists()
    assert not cfg.secrets_path(tmp_path).exists()
    assert ui.diffs  # a preview was shown


# --------------------------------------------------------------------------- #
# pull
# --------------------------------------------------------------------------- #


@respx.mock
def test_pull_restores_secret_and_updates_workspace(tmp_path):
    write_config(tmp_path)
    write_state(tmp_path)
    # Committed sanitized files + local secret value.
    sync._write_committed(tmp_path, "collections/orders.json", collection_response()["collection"])
    sync._write_committed(
        tmp_path,
        "environments/staging.json",
        {
            "name": "staging",
            "values": [
                {"key": "base_url", "value": "https://x", "type": "default"},
                {"key": "api_token", "value": "{{api_token}}", "type": "secret"},
            ],
        },
    )
    cfg.save_secrets(tmp_path, {"staging": {"api_token": "RESTORED"}})

    col_route = respx.put(f"{BASE}/collections/cuid").mock(
        return_value=httpx.Response(200, json={"collection": {"uid": "cuid"}})
    )
    env_route = respx.put(f"{BASE}/environments/euid").mock(
        return_value=httpx.Response(200, json={"environment": {"uid": "euid"}})
    )

    sync.pull(make_app(tmp_path), names=())

    assert col_route.called and env_route.called
    sent_env = json.loads(env_route.calls.last.request.content)["environment"]
    token = next(v for v in sent_env["values"] if v["key"] == "api_token")
    assert token["value"] == "RESTORED"  # secret merged back in before import


@respx.mock
def test_pull_creates_unmapped_resource_and_records_uid(tmp_path):
    write_config(tmp_path)
    write_state(tmp_path, with_uids=False)  # nothing mapped yet
    sync._write_committed(tmp_path, "collections/orders.json", collection_response()["collection"])
    # Only test the collection here.
    (tmp_path / "environments").mkdir(exist_ok=True)

    respx.post(f"{BASE}/collections").mock(
        return_value=httpx.Response(200, json={"collection": {"uid": "new-cuid"}})
    )

    sync.pull(make_app(tmp_path), names=("orders",))

    state = cfg.load_state(tmp_path)
    assert state.uid_for("collections", "orders") == "new-cuid"


@respx.mock
def test_pull_prompts_for_missing_secret(tmp_path):
    write_config(tmp_path)
    write_state(tmp_path)
    sync._write_committed(
        tmp_path,
        "environments/staging.json",
        {
            "name": "staging",
            "values": [{"key": "api_token", "value": "{{api_token}}", "type": "secret"}],
        },
    )
    sync._write_committed(tmp_path, "collections/orders.json", collection_response()["collection"])
    respx.put(f"{BASE}/collections/cuid").mock(
        return_value=httpx.Response(200, json={"collection": {}})
    )
    env_route = respx.put(f"{BASE}/environments/euid").mock(
        return_value=httpx.Response(200, json={"environment": {}})
    )

    ui = FakeUI(prompts=["typed-secret"])
    sync.pull(make_app(tmp_path, ui=ui), names=(), prompt_secrets=True)

    assert cfg.load_secrets(tmp_path)["staging"]["api_token"] == "typed-secret"
    sent = json.loads(env_route.calls.last.request.content)["environment"]
    assert sent["values"][0]["value"] == "typed-secret"


# --------------------------------------------------------------------------- #
# verify / secrets check
# --------------------------------------------------------------------------- #


def test_verify_passes_on_clean_normalized_files(tmp_path):
    write_config(tmp_path)
    sync._write_committed(tmp_path, "collections/orders.json", collection_response()["collection"])
    sync._write_committed(
        tmp_path,
        "environments/staging.json",
        {
            "name": "staging",
            "values": [{"key": "api_token", "value": "{{api_token}}", "type": "secret"}],
        },
    )
    ui = FakeUI()
    sync.verify(make_app(tmp_path, ui=ui))
    assert ui.messages["success"]


def test_verify_fails_on_unnormalized_file(tmp_path):
    write_config(tmp_path)
    (tmp_path / "collections").mkdir()
    # Deliberately not normalized (compact, unsorted, no trailing newline).
    (tmp_path / "collections/orders.json").write_text('{"item": [], "info": {}}', encoding="utf-8")
    with pytest.raises(sync.SyncError, match="verify failed"):
        sync.verify(make_app(tmp_path))


def test_verify_fails_on_secret_shaped_value(tmp_path):
    write_config(tmp_path)
    sync._write_committed(
        tmp_path,
        "collections/orders.json",
        {
            "info": {"name": "x"},
            "item": [
                {
                    "name": "c",
                    "request": {"header": [{"key": "k", "value": "AKIAIOSFODNN7EXAMPLE"}]},
                }
            ],
        },
    )
    with pytest.raises(sync.SyncError, match="verify failed"):
        sync.verify(make_app(tmp_path))


def test_secrets_check_reports_missing(tmp_path):
    write_config(tmp_path)
    sync._write_committed(
        tmp_path,
        "environments/staging.json",
        {
            "name": "staging",
            "values": [{"key": "api_token", "value": "{{api_token}}", "type": "secret"}],
        },
    )
    with pytest.raises(sync.SyncError, match="secrets check failed"):
        sync.secrets_check(make_app(tmp_path))

    cfg.save_secrets(tmp_path, {"staging": {"api_token": "x"}})
    ui = FakeUI()
    sync.secrets_check(make_app(tmp_path, ui=ui))
    assert ui.messages["success"]
