from requestnest import secrets


def make_env(values):
    return {"name": "staging", "values": values, "_postman_variable_scope": "environment"}


def test_sanitize_replaces_secret_typed_values_and_captures():
    env = make_env(
        [
            {"key": "base_url", "value": "https://api.example.com", "type": "default"},
            {"key": "api_token", "value": "super-secret-123", "type": "secret"},
        ]
    )
    sanitized, captured = secrets.sanitize_environment(env)

    assert captured == {"api_token": "super-secret-123"}
    values = {v["key"]: v["value"] for v in sanitized["values"]}
    assert values["base_url"] == "https://api.example.com"  # untouched
    assert values["api_token"] == "{{api_token}}"
    # Original object is not mutated.
    assert env["values"][1]["value"] == "super-secret-123"


def test_sanitize_honors_override_keys():
    env = make_env([{"key": "token", "value": "abc", "type": "default"}])
    sanitized, captured = secrets.sanitize_environment(env, override_keys=["token"])
    assert captured == {"token": "abc"}
    assert sanitized["values"][0]["value"] == "{{token}}"
    assert sanitized["values"][0]["type"] == "secret"


def test_sanitize_desanitize_round_trip():
    env = make_env(
        [
            {"key": "base_url", "value": "https://x", "type": "default"},
            {"key": "api_token", "value": "real", "type": "secret"},
        ]
    )
    sanitized, captured = secrets.sanitize_environment(env)
    restored, missing = secrets.desanitize_environment(sanitized, captured)
    assert missing == []
    restored_values = {v["key"]: v["value"] for v in restored["values"]}
    assert restored_values["api_token"] == "real"
    assert restored_values["base_url"] == "https://x"


def test_desanitize_reports_missing_keys():
    env = make_env([{"key": "api_token", "value": "{{api_token}}", "type": "secret"}])
    restored, missing = secrets.desanitize_environment(env, {})
    assert missing == ["api_token"]
    # Placeholder left as-is when no value available.
    assert restored["values"][0]["value"] == "{{api_token}}"


def test_needed_secret_keys_from_placeholders_and_overrides():
    env = make_env(
        [
            {"key": "api_token", "value": "{{api_token}}", "type": "secret"},
            {"key": "plain", "value": "ok", "type": "default"},
            {"key": "extra", "value": "", "type": "default"},
        ]
    )
    assert secrets.needed_secret_keys(env) == ["api_token"]
    assert secrets.needed_secret_keys(env, override_keys=["extra"]) == ["api_token", "extra"]


def test_safety_scan_flags_hardcoded_token_in_collection():
    collection = {
        "item": [
            {
                "name": "call",
                "request": {
                    "header": [{"key": "Authorization", "value": "Bearer AKIAIOSFODNN7EXAMPLE"}]
                },
            }
        ]
    }
    findings = secrets.safety_scan(collection)
    assert len(findings) == 1
    assert findings[0].pattern == "aws-access-key"
    assert findings[0].location == "$.item[0].request.header[0].value"


def test_safety_scan_ignores_placeholders_and_normal_values():
    env = make_env(
        [
            {"key": "api_token", "value": "{{api_token}}", "type": "secret"},
            {"key": "base_url", "value": "https://api.example.com", "type": "default"},
        ]
    )
    assert secrets.safety_scan(env) == []


def test_find_missing_secrets():
    required = {"staging": ["api_token", "signing_key"], "prod": ["api_token"]}
    present = {"staging": {"api_token": "x", "signing_key": ""}, "prod": {"api_token": "y"}}
    assert secrets.find_missing_secrets(required, present) == {"staging": ["signing_key"]}
