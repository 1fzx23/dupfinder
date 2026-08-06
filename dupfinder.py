#!/usr/bin/env python3
"""dupfinder — Find duplicate files by content hash.

A tiny, dependency-free command line tool that scans a directory tree,
groups files by their SHA-256 content hash, and reports duplicates along
with the disk space you could reclaim by removing them.

By default dupfinder is *read-only*: it only reports. Use ``--delete`` to
remove the *extra* copies (keeping one per group) after a confirmation.

Examples
--------
    # Scan the current directory, show duplicate groups
    python dupfinder.py .

    # Only consider files larger than 1 MB
    python dupfinder.py ~/Downloads --min-size 1048576

    # Machine-readable output
    python dupfinder.py . --json

    # Remove extra copies (keeps the first file of each group)
    python dupfinder.py ~/Downloads --delete
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

CHUNK_SIZE = 1 << 16  # 64 KiB, read in chunks to handle large files


@dataclass
class DupReport:
    """Aggregated result of a duplicate scan."""

    groups: list[list[str]] = field(default_factory=list)
    wasted_bytes: int = 0
    file_count: int = 0

    def to_dict(self) -> dict:
        return {
            "wasted_bytes": self.wasted_bytes,
            "file_count": self.file_count,
            "group_count": len(self.groups),
            "groups": [{"files": g, "size": _size_of(g[0])} for g in self.groups],
        }


def _size_of(path: str) -> int:
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def human_size(num: int) -> str:
    """Format a byte count into a human readable string."""
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if value < 1024 or unit == "PB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024


def compute_hash(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan(root: Path, min_size: int, follow_links: bool = False) -> DupReport:
    """Walk *root*, group duplicate files, and build a report."""
    # Pass 1: bucket by size so we only hash files that *could* collide.
    by_size: dict[int, list[Path]] = defaultdict(list)
    walker = root.rglob("*")
    if not follow_links:
        walker = (p for p in walker if not p.is_symlink())

    for path in walker:
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size < min_size:
            continue
        by_size[size].append(path)

    # Pass 2: hash the candidates that share a size.
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for paths in by_size.values():
        if len(paths) < 2:
            continue
        for p in paths:
            try:
                file_hash = compute_hash(p)
            except OSError:
                continue
            by_hash[file_hash].append(p)

    groups: list[list[str]] = []
    wasted = 0
    for paths in by_hash.values():
        if len(paths) < 2:
            continue
        str_paths = [str(p) for p in paths]
        groups.append(str_paths)
        # Keep one copy, the rest are reclaimable.
        wasted += sum(p.stat().st_size for p in paths[1:])

    groups.sort(key=lambda g: _size_of(g[0]), reverse=True)
    return DupReport(groups=groups, wasted_bytes=wasted, file_count=sum(len(g) for g in groups))


def render_text(report: DupReport) -> str:
    lines: list[str] = []
    if not report.groups:
        lines.append("No duplicate files found. 🎉")
        return "\n".join(lines)

    lines.append(f"Found {len(report.groups)} duplicate group(s), "
                 f"{report.file_count} files involved.")
    lines.append(f"Reclaimable space: {human_size(report.wasted_bytes)}")
    lines.append("=" * 60)
    for idx, group in enumerate(report.groups, start=1):
        size = human_size(_size_of(group[0]))
        lines.append(f"\n[{idx}] {len(group)} copies · {size} each")
        for fp in group:
            lines.append(f"    {fp}")
    return "\n".join(lines)


def delete_extras(report: DupReport) -> int:
    """Remove every copy except the first in each group. Returns count deleted."""
    removed = 0
    for group in report.groups:
        for fp in group[1:]:
            try:
                Path(fp).unlink()
                removed += 1
                print(f"removed: {fp}")
            except OSError as exc:
                print(f"FAILED  : {fp} ({exc})", file=sys.stderr)
    return removed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dupfinder",
        description="Find duplicate files by content hash.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Directory to scan (default: .)")
    parser.add_argument("--min-size", type=int, default=0,
                        help="Ignore files smaller than this many bytes.")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    parser.add_argument("--delete", action="store_true",
                        help="Delete extra copies after confirmation (keeps the first).")
    parser.add_argument("--yes", action="store_true",
                        help="With --delete, skip the confirmation prompt.")
    parser.add_argument("--follow-links", action="store_true",
                        help="Follow symbolic links (off by default).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.path).expanduser()
    if not root.exists() or not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    report = scan(root, min_size=args.min_size, follow_links=args.follow_links)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_text(report))

    if args.delete:
        if not report.groups:
            return 0
        if not args.yes:
            answer = input(f"\nDelete {sum(len(g) - 1 for g in report.groups)} extra "
                           f"copy/copies? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Aborted. No files were deleted.")
                return 0
        removed = delete_extras(report)
        print(f"\nDone. Removed {removed} file(s), "
              f"reclaimed {human_size(report.wasted_bytes)}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
