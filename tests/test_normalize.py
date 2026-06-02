from requestnest import normalize


def test_strip_volatile_removes_ids_and_timestamps_recursively():
    obj = {
        "info": {"_postman_id": "abc", "name": "API"},
        "item": [
            {"id": "1", "name": "req", "request": {"method": "GET"}},
            {"id": "2", "name": "folder", "item": [{"id": "3", "name": "nested"}]},
        ],
        "createdAt": "2020-01-01",
    }
    cleaned = normalize.strip_volatile(obj)
    assert cleaned == {
        "info": {"name": "API"},
        "item": [
            {"name": "req", "request": {"method": "GET"}},
            {"name": "folder", "item": [{"name": "nested"}]},
        ],
    }


def test_strip_volatile_keeps_form_field_named_id():
    # A form field's structural key is "key"/"value", not "id" — must be kept.
    obj = {"item": [{"key": "id", "value": "42", "type": "text"}]}
    assert normalize.strip_volatile(obj) == obj


def test_array_order_is_preserved():
    obj = {"item": [{"name": "b"}, {"name": "a"}, {"name": "c"}]}
    text = normalize.normalize(obj)
    # Names must appear in original order despite sort_keys on objects.
    assert text.index('"b"') < text.index('"a"') < text.index('"c"')


def test_normalize_is_idempotent():
    obj = {
        "info": {"name": "API", "_postman_id": "x"},
        "item": [{"id": "1", "name": "z"}, {"id": "2", "name": "a"}],
    }
    once = normalize.normalize(obj)
    twice = normalize.normalize_text(once)
    assert once == twice


def test_normalize_ends_with_single_trailing_newline():
    text = normalize.normalize({"a": 1})
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
