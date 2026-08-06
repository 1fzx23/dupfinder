"""Smoke tests for dupfinder (run with: python -m tests.test_dupfinder)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dupfinder  # noqa: E402


def _make_tree(root: Path) -> None:
    (root / "a.txt").write_text("hello")
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "b.txt").write_text("hello")          # duplicate of a.txt
    (root / "sub" / "c.txt").write_text("world")          # unique
    (root / "sub" / "d.txt").write_text("world")          # duplicate of c.txt
    (root / "sub" / "e.txt").write_text("unique-content")  # unique


def test_scan_finds_two_groups(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    report = dupfinder.scan(tmp_path, min_size=0)
    assert len(report.groups) == 2, report.groups
    # Both groups should have exactly 2 files (hello + world).
    for group in report.groups:
        assert len(group) == 2
    # Reclaimable = one "hello" (5 bytes) + one "world" (5 bytes) = 10 bytes.
    assert report.wasted_bytes == 10, report.wasted_bytes


def test_min_size_filters_small_files(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    # "hello" and "world" are 5 bytes; bump min-size above that → no groups.
    report = dupfinder.scan(tmp_path, min_size=100)
    assert report.groups == []


def test_json_output_is_valid(tmp_path: Path) -> None:
    _make_tree(tmp_path)
    report = dupfinder.scan(tmp_path, min_size=0)
    data = report.to_dict()
    assert data["group_count"] == 2
    assert data["wasted_bytes"] == 10


if __name__ == "__main__":
    import tempfile

    for test in (test_scan_finds_two_groups,
                 test_min_size_filters_small_files,
                 test_json_output_is_valid):
        tmp = Path(tempfile.mkdtemp())
        try:
            test(tmp)
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)
    print("All tests passed ✓")
