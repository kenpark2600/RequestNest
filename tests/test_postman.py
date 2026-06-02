import httpx
import pytest
import respx

from requestnest import postman
from requestnest.postman import (
    PostmanAPIError,
    PostmanAuthError,
    PostmanClient,
)

BASE = postman.BASE_URL


def make_client(**kwargs) -> PostmanClient:
    # No real sleeping during retry tests.
    kwargs.setdefault("sleep", lambda _s: None)
    return PostmanClient("PMAK-test", **kwargs)


@respx.mock
def test_me_returns_user():
    respx.get(f"{BASE}/me").mock(return_value=httpx.Response(200, json={"user": {"id": 42}}))
    with make_client() as client:
        assert client.me() == {"id": 42}


@respx.mock
def test_get_collection_unwraps_inner_object():
    respx.get(f"{BASE}/collections/uid-1").mock(
        return_value=httpx.Response(200, json={"collection": {"info": {"name": "API"}}})
    )
    with make_client() as client:
        assert client.get_collection("uid-1") == {"info": {"name": "API"}}


@respx.mock
def test_create_collection_wraps_body_and_unwraps_response():
    route = respx.post(f"{BASE}/collections").mock(
        return_value=httpx.Response(200, json={"collection": {"uid": "new-uid"}})
    )
    with make_client() as client:
        result = client.create_collection({"info": {"name": "API"}})
    assert result == {"uid": "new-uid"}
    assert route.calls.last.request.headers["X-Api-Key"] == "PMAK-test"
    import json

    sent = json.loads(route.calls.last.request.content)
    assert sent == {"collection": {"info": {"name": "API"}}}


@respx.mock
def test_auth_error_raised_on_401():
    respx.get(f"{BASE}/me").mock(return_value=httpx.Response(401, json={"error": {"name": "x"}}))
    with make_client() as client, pytest.raises(PostmanAuthError):
        client.me()


@respx.mock
def test_api_error_includes_message():
    respx.get(f"{BASE}/collections/bad").mock(
        return_value=httpx.Response(404, json={"error": {"message": "not found"}})
    )
    with make_client() as client:
        with pytest.raises(PostmanAPIError) as exc_info:
            client.get_collection("bad")
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value)


@respx.mock
def test_retries_on_429_then_succeeds():
    route = respx.get(f"{BASE}/environments")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"environments": [{"uid": "e1"}]}),
    ]
    with make_client() as client:
        envs = client.list_environments()
    assert envs == [{"uid": "e1"}]
    assert route.call_count == 2


@respx.mock
def test_gives_up_after_max_retries():
    respx.get(f"{BASE}/environments").mock(return_value=httpx.Response(503))
    with make_client(max_retries=2) as client:
        with pytest.raises(PostmanAPIError) as exc_info:
            client.list_environments()
    assert exc_info.value.status_code == 503
