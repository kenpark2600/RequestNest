from requestnest import semantic_diff


def collection(items):
    return {"info": {"name": "API"}, "item": items}


def req(name, method="GET", url="https://x", extra=None):
    request = {"method": method, "url": url}
    if extra:
        request.update(extra)
    return {"name": name, "request": request}


def test_collection_added_removed_changed():
    old = collection(
        [
            req("login", method="POST"),
            req("get-user"),
            {"name": "admin", "item": [req("delete-user", method="DELETE")]},
        ]
    )
    new = collection(
        [
            req("login", method="POST"),
            req("get-user", method="POST"),  # changed method
            req("new-endpoint"),  # added
            # admin/delete-user removed
        ]
    )
    result = semantic_diff.diff_collections(old, new, label="orders-api")
    summary = result.summary()
    assert "+ new-endpoint" in summary
    assert "- admin/delete-user" in summary
    assert "~ get-user (method)" in summary
    assert "login" not in " ".join(summary)  # unchanged not reported


def test_collection_ignores_volatile_ids():
    old = {"info": {"name": "API", "_postman_id": "a"}, "item": [{"id": "1", **req("x")}]}
    new = {"info": {"name": "API", "_postman_id": "b"}, "item": [{"id": "2", **req("x")}]}
    assert semantic_diff.diff_collections(old, new).is_empty


def env(values):
    return {"name": "staging", "values": values}


def test_environment_diff_reports_keys_not_values():
    old = env(
        [
            {"key": "base_url", "value": "https://old", "type": "default"},
            {"key": "api_token", "value": "{{api_token}}", "type": "secret"},
            {"key": "gone", "value": "x", "type": "default"},
        ]
    )
    new = env(
        [
            {"key": "base_url", "value": "https://new", "type": "default"},
            {"key": "api_token", "value": "{{api_token}}", "type": "secret"},
            {"key": "added", "value": "y", "type": "default"},
        ]
    )
    result = semantic_diff.diff_environments(old, new)
    summary = result.summary()
    assert "+ added" in summary
    assert "- gone" in summary
    assert "~ base_url (value)" in summary
    # The actual changed value must never appear in the diff output.
    assert "https://new" not in " ".join(summary)
