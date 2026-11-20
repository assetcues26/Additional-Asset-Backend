from additional_asset.utils.helpers import to_int_or_none, truncate_for_phase2


def test_to_int_or_none():
    assert to_int_or_none("12") == 12
    assert to_int_or_none(12.0) == 12
    assert to_int_or_none(0) is None
    assert to_int_or_none("abc") is None
    assert to_int_or_none(None) is None


def test_truncate():
    assert truncate_for_phase2("hello", 10) == "hello"
    assert truncate_for_phase2("abcdefghijXXX", 10).startswith("abcdefghij")
