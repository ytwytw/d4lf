from src.tools.public_safety.models import Finding, deduplicate


def test_deduplicate_sorts_and_removes_identical_findings() -> None:
    second = Finding("b", "z.txt", "second", 2)
    first = Finding("a", "a.txt", "first", 1)

    assert deduplicate([second, first, first]) == [first, second]
