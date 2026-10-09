import pytest

from hrcek.core.navigation import safe_next


def test_safe_next_keeps_a_local_path(rf):
    request = rf.get("/x", {"next": "/entries/?page=2"})
    assert safe_next(request, "/fallback/") == "/entries/?page=2"


def test_safe_next_prefers_post_over_get(rf):
    request = rf.post("/x", {"next": "/entries/?page=2"}, QUERY_STRING="next=/other/")
    assert safe_next(request, "/fallback/") == "/entries/?page=2"


@pytest.mark.parametrize("target", ["https://evil.example/", "//evil.example/", ""])
def test_safe_next_refuses_anything_else(rf, target):
    request = rf.get("/x", {"next": target})
    assert safe_next(request, "/fallback/") == "/fallback/"


def test_safe_next_falls_back_when_there_is_no_next(rf):
    request = rf.get("/x")
    assert safe_next(request, "/fallback/") == "/fallback/"
