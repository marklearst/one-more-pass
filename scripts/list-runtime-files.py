#!/usr/bin/env python3
"""List the installable One More Pass runtime and its SHA-256 checksums."""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Iterable
from pathlib import Path


ROOT_FILES = ("LICENSE",)
RUNTIME_DIRECTORIES = (
    ".claude-plugin",
    ".codex-plugin",
    "skills",
)
EXCLUDED_PARTS = {
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".reports",
    ".ruff_cache",
    "__pycache__",
    "docs",
    "node_modules",
    "reports",
    "tests",
    "tmp",
}
EXCLUDED_SUFFIXES = {".diff", ".log", ".patch", ".pyc", ".pyo", ".tmp"}


class InventoryError(ValueError):
    """Raised when the runtime tree cannot be inventoried safely."""


def is_excluded(relative_path: Path) -> bool:
    if any(part in EXCLUDED_PARTS for part in relative_path.parts):
        return True
    if any(part.startswith(".") for part in relative_path.parts[1:]):
        return True
    return relative_path.suffix.lower() in EXCLUDED_SUFFIXES


def require_regular_file(path: Path, root: Path) -> None:
    relative_path = path.relative_to(root).as_posix()
    if path.is_symlink():
        raise InventoryError(f"runtime path is a symlink: {relative_path}")
    if not path.is_file():
        raise InventoryError(f"required runtime file is missing: {relative_path}")
    if not path.resolve().is_relative_to(root):
        raise InventoryError(f"runtime path escapes plugin root: {relative_path}")


def runtime_files(root: Path) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        raise InventoryError(f"plugin root is not a directory: {root}")

    allowed_top_level = {*ROOT_FILES, *RUNTIME_DIRECTORIES}
    for path in root.iterdir():
        if path.name not in allowed_top_level:
            raise InventoryError(
                f"unexpected runtime entry: {path.relative_to(root).as_posix()}"
            )
        if path.is_symlink():
            raise InventoryError(
                f"runtime path is a symlink: {path.relative_to(root).as_posix()}"
            )

    files: list[Path] = []
    for relative_path in ROOT_FILES:
        path = root / relative_path
        require_regular_file(path, root)
        files.append(path)

    for relative_directory in RUNTIME_DIRECTORIES:
        directory = root / relative_directory
        if directory.is_symlink():
            raise InventoryError(f"runtime directory is a symlink: {relative_directory}")
        if not directory.is_dir():
            raise InventoryError(f"required runtime directory is missing: {relative_directory}")

        for path in directory.rglob("*"):
            relative_path = path.relative_to(root)
            if is_excluded(relative_path):
                raise InventoryError(
                    f"forbidden runtime entry: {relative_path.as_posix()}"
                )
            if path.is_symlink():
                raise InventoryError(
                    f"runtime path is a symlink: {relative_path.as_posix()}"
                )
            if path.is_file():
                require_regular_file(path, root)
                files.append(path)
            elif not path.is_dir():
                raise InventoryError(
                    f"runtime path is not a regular file or directory: "
                    f"{relative_path.as_posix()}"
                )

    return sorted(set(files), key=lambda path: path.relative_to(root).as_posix())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def render_inventory(root: Path, files: Iterable[Path]) -> str:
    records: list[tuple[str, str]] = []
    for path in files:
        relative_path = path.relative_to(root).as_posix()
        records.append((relative_path, sha256_file(path)))

    package_digest = hashlib.sha256()
    lines: list[str] = []
    for relative_path, digest in records:
        lines.append(f"{digest}  {relative_path}")
        package_digest.update(relative_path.encode("utf-8"))
        package_digest.update(b"\0")
        package_digest.update(digest.encode("ascii"))
        package_digest.update(b"\n")
    lines.append(f"PACKAGE_SHA256  {package_digest.hexdigest()}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List and hash files in the installable plugin runtime."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "plugins" / "one-more-pass",
        help="plugin root (defaults to plugins/one-more-pass)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    try:
        files = runtime_files(root)
    except (InventoryError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(render_inventory(root, files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
