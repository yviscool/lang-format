from __future__ import annotations

import argparse
import fnmatch
import hashlib
import subprocess
import zipfile
from pathlib import Path


SKIP_DIR_NAMES = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Sublime Text package and a matching SHA256 checksum."
    )
    parser.add_argument("--mode", choices=("subtree", "git-files"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-dir")
    parser.add_argument("--exclude", action="append", default=[])
    return parser.parse_args()


def should_skip(relative_path: Path, patterns: list[str]) -> bool:
    if any(part in SKIP_DIR_NAMES for part in relative_path.parts):
        return True
    if relative_path.suffix in SKIP_SUFFIXES:
        return True
    path_text = relative_path.as_posix()
    return any(fnmatch.fnmatch(path_text, pattern) for pattern in patterns)


def iter_subtree_files(source_dir: Path, patterns: list[str]) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_dir():
            continue
        relative_path = path.relative_to(source_dir)
        if should_skip(relative_path, patterns):
            continue
        files.append((path, relative_path.as_posix()))
    return files


def iter_git_files(patterns: list[str]) -> list[tuple[Path, str]]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=False,
    )
    files: list[tuple[Path, str]] = []
    for entry in result.stdout.split(b"\x00"):
        if not entry:
            continue
        relative_text = entry.decode("utf-8")
        relative_path = Path(relative_text)
        if should_skip(relative_path, patterns):
            continue
        absolute_path = Path.cwd() / relative_path
        if absolute_path.is_dir():
            continue
        files.append((absolute_path, relative_path.as_posix()))
    return files


def build_archive(files: list[tuple[Path, str]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source_path, archive_path in files:
            archive.write(source_path, archive_path)
    return output_path


def write_checksum(output_path: Path) -> Path:
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    checksum_path = output_path.with_suffix(output_path.suffix + ".sha256")
    checksum_path.write_text(f"{digest}  {output_path.name}\n", encoding="utf-8")
    return checksum_path


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)
    if args.mode == "subtree":
        if not args.source_dir:
            raise SystemExit("--source-dir is required when --mode=subtree")
        source_dir = Path(args.source_dir)
        if not source_dir.is_dir():
            raise SystemExit(f"Missing source directory: {source_dir}")
        files = iter_subtree_files(source_dir, args.exclude)
    else:
        files = iter_git_files(args.exclude)

    if not files:
        raise SystemExit("No files matched the release package selection.")

    archive_path = build_archive(files, output_path)
    checksum_path = write_checksum(archive_path)
    print(f"Built {archive_path}")
    print(f"Wrote {checksum_path}")


if __name__ == "__main__":
    main()
