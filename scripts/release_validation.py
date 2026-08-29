#!/usr/bin/env python3
"""Validate release metadata and build a fixed-name release bundle.

The release workflow runs this module before any repository-write capability is
available.  It deliberately accepts only the small metadata shape used by this
repository and copies release inputs to fixed bundle names so publication never
receives an arbitrary path from release/rc.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable


RELEASE_TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+$")
RELEASE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .:_()/-]{0,119}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
APPROVED_KEYS = frozenset({"tag", "name", "notes"})
REQUIRED_CHECKS = frozenset({"test", "frontend-render"})
ASSET_SOURCES = (
    ("vista-keypad-card.js", Path("frontend/vista-keypad-card.js")),
    ("vista-keypad-simulator.html", Path("frontend/vista-keypad-simulator.html")),
)


class ReleaseValidationError(ValueError):
    """Raised when release metadata or a release bundle is unsafe."""


def _repo_root_for(metadata_path: Path) -> Path:
    resolved = metadata_path.resolve()
    if resolved.name != "rc.json" or resolved.parent.name != "release":
        raise ReleaseValidationError("metadata must be release/rc.json")
    return resolved.parent.parent


def _validate_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseValidationError(f"{field} must be a non-empty string")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        raise ReleaseValidationError(f"{field} contains a control character")
    return value


def _validate_notes_path(notes: Any, repo_root: Path) -> Path:
    notes_value = _validate_string(notes, "notes")
    if "\\" in notes_value:
        raise ReleaseValidationError("notes must use repository-relative POSIX separators")

    relative = Path(notes_value)
    if relative.is_absolute() or not relative.parts:
        raise ReleaseValidationError("notes must be a relative path")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise ReleaseValidationError("notes may not contain traversal components")
    if relative.parts[0] != "release" or relative.suffix != ".md":
        raise ReleaseValidationError("notes must be a Markdown file below release/")

    release_dir = (repo_root / "release").resolve()
    candidate = repo_root / relative
    if candidate.is_symlink():
        raise ReleaseValidationError("notes may not be a symlink")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(release_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise ReleaseValidationError("notes must resolve below release/") from exc
    if not resolved.is_file():
        raise ReleaseValidationError("notes must name a regular file")
    return resolved


def load_release_metadata(metadata_path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load and validate release/rc.json, returning canonical resolved data."""

    metadata_file = Path(metadata_path)
    repo_root = _repo_root_for(metadata_file)
    try:
        with metadata_file.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseValidationError(f"cannot read valid JSON from {metadata_file}") from exc

    if not isinstance(document, dict) or frozenset(document) != APPROVED_KEYS:
        raise ReleaseValidationError("release metadata must contain exactly tag, name, and notes")

    tag = _validate_string(document["tag"], "tag")
    if not RELEASE_TAG_RE.fullmatch(tag):
        raise ReleaseValidationError("tag does not match vMAJOR.MINOR.PATCH-rc.NUMBER")

    name = _validate_string(document["name"], "name")
    if len(name) > 120 or not RELEASE_NAME_RE.fullmatch(name):
        raise ReleaseValidationError("name contains unsupported characters or is too long")

    notes_path = _validate_notes_path(document["notes"], repo_root)
    return {
        "tag": tag,
        "name": name,
        "notes": document["notes"],
        "notes_path": str(notes_path),
        "repo_root": str(repo_root),
    }


def _copy_regular_file(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ReleaseValidationError(f"release asset is not a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def create_release_bundle(
    metadata: dict[str, Any], bundle_dir: str | os.PathLike[str], commit: str
) -> dict[str, Any]:
    """Copy approved release inputs to fixed names and write their manifest."""

    if not COMMIT_RE.fullmatch(commit):
        raise ReleaseValidationError("release commit must be a full commit SHA")
    bundle = Path(bundle_dir)
    if bundle.exists():
        raise ReleaseValidationError("release bundle directory already exists")
    bundle.mkdir(parents=True)

    repo_root = Path(metadata["repo_root"])
    notes_destination = bundle / "notes.md"
    _copy_regular_file(Path(metadata["notes_path"]), notes_destination)

    assets: list[dict[str, Any]] = []
    for asset_name, relative_source in ASSET_SOURCES:
        source = repo_root / relative_source
        destination = bundle / asset_name
        _copy_regular_file(source, destination)
        digest, size = _sha256_and_size(destination)
        assets.append({"name": asset_name, "sha256": digest, "size": size})

    notes_digest, notes_size = _sha256_and_size(notes_destination)
    manifest = {
        "schema": 1,
        "commit": commit,
        "tag": metadata["tag"],
        "name": metadata["name"],
        "notes": {"name": "notes.md", "sha256": notes_digest, "size": notes_size},
        "assets": assets,
    }
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def successful_required_checks(check_runs: Iterable[dict[str, Any]]) -> bool:
    """Return true only when the newest required Actions checks succeeded."""

    latest: dict[str, dict[str, Any]] = {}
    for check in check_runs:
        if not isinstance(check, dict):
            continue
        name = check.get("name")
        app = check.get("app")
        if name not in REQUIRED_CHECKS or not isinstance(app, dict) or app.get("slug") != "github-actions":
            continue
        try:
            check_id = int(check.get("id", 0))
        except (TypeError, ValueError):
            continue
        previous = latest.get(name)
        if previous is None or check_id > int(previous.get("id", 0)):
            latest[name] = check

    return all(
        latest.get(name, {}).get("status") == "completed"
        and latest.get(name, {}).get("conclusion") == "success"
        for name in REQUIRED_CHECKS
    )


def tag_points_to_commit(tag_sha: str, expected_commit: str) -> bool:
    """Check a dereferenced tag target without accepting abbreviated SHAs."""

    return (
        bool(COMMIT_RE.fullmatch(tag_sha) and COMMIT_RE.fullmatch(expected_commit))
        and tag_sha == expected_commit
    )


def release_metadata_matches(release: dict[str, Any], tag: str) -> bool:
    """Reject an existing release that is not the expected prerelease record."""

    return (
        isinstance(release, dict)
        and release.get("tag_name") == tag
        and release.get("prerelease") is True
        and release.get("draft") is False
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", nargs="?", help="path to release/rc.json")
    parser.add_argument("--bundle-dir")
    parser.add_argument("--commit")
    parser.add_argument(
        "--check-runs-stdin",
        action="store_true",
        help="read a GitHub check-runs JSON response and validate required checks",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.check_runs_stdin:
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError:
            return 1
        return 0 if successful_required_checks(payload.get("check_runs", [])) else 1
    if not args.metadata:
        raise SystemExit("metadata is required unless --check-runs-stdin is used")

    metadata = load_release_metadata(args.metadata)
    if args.bundle_dir:
        if not args.commit:
            raise SystemExit("--commit is required with --bundle-dir")
        create_release_bundle(metadata, args.bundle_dir, args.commit)
    print(json.dumps({key: metadata[key] for key in ("tag", "name", "notes")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseValidationError as error:
        print(f"release metadata rejected: {error}", file=sys.stderr)
        raise SystemExit(1)
