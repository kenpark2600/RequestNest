from requestnest import conflict


def test_no_conflict_when_up_to_date():
    report = conflict.assess(behind=0, upstream_changed_paths=[], pushing_paths=["a.json"])
    assert not report.has_conflict
    assert "Up to date" in report.message()


def test_no_conflict_when_behind_but_disjoint():
    report = conflict.assess(
        behind=2, upstream_changed_paths=["other.json"], pushing_paths=["a.json"]
    )
    assert not report.has_conflict
    assert "none touch" in report.message()


def test_conflict_when_upstream_touched_pushed_file():
    report = conflict.assess(
        behind=1,
        upstream_changed_paths=["collections/orders.json", "x.json"],
        pushing_paths=["collections/orders.json"],
    )
    assert report.has_conflict
    assert report.affected == ["collections/orders.json"]
    assert "pull" in report.message().lower()
