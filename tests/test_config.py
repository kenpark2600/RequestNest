import pytest

from requestnest import config


def test_config_round_trip(tmp_path):
    cfg = config.Config(
        collections=[config.Collection(name="orders-api", path="collections/orders-api.json")],
        environments=[
            config.Environment(
                name="staging",
                path="environments/staging.json",
                secrets=["api_token", "signing_key"],
            )
        ],
        git=config.GitConfig(branch="develop", auto_push=False),
    )
    config.save_config(tmp_path, cfg)
    loaded = config.load_config(tmp_path)

    assert loaded.collections[0].name == "orders-api"
    assert loaded.environments[0].secrets == ["api_token", "signing_key"]
    assert loaded.git.branch == "develop"
    assert loaded.git.auto_push is False
    assert loaded.git.auto_commit is True  # default preserved


def test_load_config_missing_raises(tmp_path):
    with pytest.raises(config.ConfigNotFoundError):
        config.load_config(tmp_path)


def test_environment_without_secrets_is_omitted_from_yaml(tmp_path):
    cfg = config.Config(
        environments=[config.Environment(name="prod", path="environments/prod.json")]
    )
    config.save_config(tmp_path, cfg)
    text = config.config_path(tmp_path).read_text(encoding="utf-8")
    assert "secrets" not in text


def test_state_round_trip_and_uid_helpers(tmp_path):
    state = config.LocalState(api_key="PMAK-xyz", workspace_id="ws1")
    state.set_uid("collections", "orders-api", "uid-123")
    config.save_state(tmp_path, state)

    loaded = config.load_state(tmp_path)
    assert loaded.api_key == "PMAK-xyz"
    assert loaded.uid_for("collections", "orders-api") == "uid-123"
    assert loaded.uid_for("environments", "missing") is None


def test_resolve_api_key_env_var_overrides_state():
    state = config.LocalState(api_key="from-state")
    assert config.resolve_api_key(state, env={}) == "from-state"
    assert config.resolve_api_key(state, env={config.API_KEY_ENV_VAR: "from-env"}) == "from-env"


def test_secrets_round_trip(tmp_path):
    secrets = {"staging": {"api_token": "real-token"}, "prod": {"api_token": "prod-token"}}
    config.save_secrets(tmp_path, secrets)
    assert config.load_secrets(tmp_path) == secrets


def test_secrets_example_has_keys_but_no_values(tmp_path):
    config.write_secrets_example(tmp_path, {"staging": ["api_token", "signing_key"]})
    text = config.secrets_example_path(tmp_path).read_text(encoding="utf-8")
    assert "api_token" in text
    assert "signing_key" in text
    assert "real-token" not in text


def test_find_repo_root_walks_up_to_config(tmp_path):
    config.save_config(tmp_path, config.Config())
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    assert config.find_repo_root(nested) == tmp_path.resolve()


def test_find_repo_root_returns_start_when_no_config(tmp_path):
    nested = tmp_path / "sub"
    nested.mkdir()
    assert config.find_repo_root(nested) == nested.resolve()


def test_ensure_gitignored_appends_missing_entries(tmp_path):
    added = config.ensure_gitignored(tmp_path)
    assert set(added) == set(config.GITIGNORED_FILES)
    # Idempotent: a second call adds nothing.
    assert config.ensure_gitignored(tmp_path) == []
    assert config.missing_gitignore_entries(tmp_path) == []
