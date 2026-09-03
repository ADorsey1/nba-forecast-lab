"""Scan project text files for common accidentally committed secrets."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SKIP_DIRECTORIES = {".git", ".pytest_cache", ".sheet_inspect", ".venv", "__pycache__", "llimllib_nba_data"}
SKIP_FILES = {Path(__file__).resolve()}
SECRET_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{20,}")),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|client[_-]?secret|access[_-]?token|password)\b\s*[:=]\s*['\"][^'\"]{12,}['\"]"
        ),
    ),
)


def _is_candidate(path: Path, root: Path) -> bool:
    if path.resolve() in SKIP_FILES:
        return False
    if any(part in SKIP_DIRECTORIES for part in path.relative_to(root).parts):
        return False
    try:
        return path.stat().st_size <= 5_000_000 and b"\x00" not in path.read_bytes()[:4096]
    except OSError:
        return False


def find_secrets(root: Path) -> list[tuple[Path, int, str]]:
    findings: list[tuple[Path, int, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or not _is_candidate(path, root):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines, start=1):
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append((path.relative_to(root), line_number, name))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    findings = find_secrets(args.root.resolve())
    if findings:
        for path, line_number, name in findings:
            print(f"{path}:{line_number}: {name}")
        return 1
    print("security audit: no likely secrets found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
