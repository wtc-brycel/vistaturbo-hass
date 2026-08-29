#!/usr/bin/env python3
"""Read-only repository guardrails for the reviewed supply-chain patterns."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.release_validation import ReleaseValidationError, load_release_metadata


ACTION_USE_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)(?:\s+#\s*(.*))?\s*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CHECKOUT_RE = re.compile(r"actions/checkout@")


def _workflow_files(root: Path) -> list[Path]:
    workflow_root = root / ".github" / "workflows"
    return sorted(
        path for path in workflow_root.iterdir() if path.suffix in {".yml", ".yaml"}
    )


def _check_action_pins(path: Path, text: str, errors: list[str]) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = ACTION_USE_RE.match(line)
        if not match:
            continue
        reference, comment = match.groups()
        if reference.startswith("./") or reference.startswith("docker://"):
            continue
        if "@" not in reference:
            errors.append(f"{path}:{line_number}: action has no immutable ref")
            continue
        _, ref = reference.rsplit("@", 1)
        if not SHA_RE.fullmatch(ref):
            errors.append(f"{path}:{line_number}: action ref is not a full commit SHA")
        if not comment or not re.search(r"\bv[0-9]+(?:\.[0-9]+)+\b", comment):
            errors.append(f"{path}:{line_number}: immutable action pin needs an upstream version comment")


def _check_checkout_credentials(path: Path, text: str, errors: list[str]) -> None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not CHECKOUT_RE.search(line):
            continue
        window = "\n".join(lines[index : index + 8])
        if not re.search(r"persist-credentials:\s*false\b", window):
            errors.append(f"{path}:{index + 1}: checkout must set persist-credentials: false")


def _check_workflow(path: Path, text: str, errors: list[str]) -> None:
    _check_action_pins(path, text, errors)
    _check_checkout_credentials(path, text, errors)
    if path.name == "tests.yml":
        if re.search(r"contents:\s*write\b", text, re.IGNORECASE):
            errors.append(f"{path}: normal test workflow grants contents: write")
        lines = text.splitlines()
        permissions_block = []
        for index, line in enumerate(lines):
            if line.strip() == "permissions:":
                permissions_block = lines[index + 1 :]
                break
        declared_read = any(
            re.fullmatch(r"[ \t]+contents:[ \t]*read[ \t]*", line, re.IGNORECASE)
            for line in permissions_block
        )
        if not declared_read:
            errors.append(f"{path}: normal test workflow must declare contents: read")
        if re.search(r"\bgit\s+(?:commit|push)\b", text, re.IGNORECASE):
            errors.append(f"{path}: normal test workflow must not commit or push")
    elif re.search(r"contents:\s*write\b", text, re.IGNORECASE) and path.name != "publish-release-candidate.yml":
        errors.append(f"{path}: unexpected write-capable workflow")


def _check_dockerfiles(root: Path, errors: list[str]) -> None:
    dockerfiles: list[Path] = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in {".git", "upload", "node_modules"}]
        dockerfiles.extend(Path(directory) / name for name in filenames if name.startswith("Dockerfile"))
    for path in sorted(dockerfiles):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*FROM\s+\S+:latest(?:\s|$)", text, re.IGNORECASE | re.MULTILINE):
            errors.append(f"{path}: production base image may not use :latest")


def check_repository(root: str | Path) -> list[str]:
    root_path = Path(root).resolve()
    errors: list[str] = []
    workflow_root = root_path / ".github" / "workflows"
    if not workflow_root.is_dir():
        errors.append(".github/workflows is missing")
    else:
        for path in _workflow_files(root_path):
            _check_workflow(path, path.read_text(encoding="utf-8"), errors)

    _check_dockerfiles(root_path, errors)
    try:
        load_release_metadata(root_path / "release" / "rc.json")
    except (OSError, ReleaseValidationError) as error:
        errors.append(f"release/rc.json: {error}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv or sys.argv[1:])
    errors = check_repository(args.root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("repository security guardrails passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
