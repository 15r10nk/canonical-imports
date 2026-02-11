from canonical_imports._core import is_private


def test_is_private():
    assert is_private("_a")
    assert not is_private("a")
    assert not is_private("__a")
