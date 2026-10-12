"""Freeze a local source snapshot without reading secrets or copying corpus data.

The dependency file is an installed-version snapshot, not a portable lockfile.
No database access, model download, migration or application startup is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import platform
import subprocess
import sys
import tomllib
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT_FILES = ("AGENTS.md", "README.md", "pyproject.toml", "alembic.ini", ".env.example", ".gitignore", "Makefile")
TREE_RULES = {
    "app": {".py", ".png", ".yaml"},
    "tests": {".py"},
    "scripts": {".py", ".ps1", ".cmd"},
    "alembic": {".py", ".mako"},
    "docs": {".md", ".yaml", ".json"},
}
EXCLUSIONS = [
    ".env and credentials",
    ".git",
    "virtual environments and caches",
    "data (PDF/OCR/indexes/reviews/backups)",
    "tmp",
    "output",
    "handoffs",
    "presentations",
    "logs",
    "external model caches",
]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    name = PurePosixPath(relative)
    if name.is_absolute() or not name.parts or any(p in {"..", "."} or ":" in p or "\\" in p for p in name.parts):
        raise ValueError(f"Unsafe relative path: {relative}")
    path = root.joinpath(*name.parts)
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError(f"Path escapes snapshot root: {relative}")
    return path


def selected_paths(root: Path) -> list[str]:
    names = set(ROOT_FILES)
    for tree, extensions in TREE_RULES.items():
        for path in (root / tree).rglob("*"):
            if "__pycache__" not in path.parts and path.is_file() and path.suffix in extensions:
                names.add(path.relative_to(root).as_posix())
    for name in names:
        if not safe_path(root, name).is_file():
            raise FileNotFoundError(name)
    return sorted(names)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, encoding="utf-8").stdout.strip()


def dependency_snapshot(root: Path) -> dict[str, object]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    roots = [*project["dependencies"], *project["optional-dependencies"]["dev"], "httpx", "ocrmypdf"]
    pending = [Requirement(value) for value in roots]
    visited: set[tuple[str, tuple[str, ...]]] = set()
    versions: dict[str, str] = {}
    mismatches: list[str] = []
    missing: list[str] = []
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        key = (name, tuple(sorted(requirement.extras)))
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            missing.append(str(requirement))
            continue
        versions[name] = distribution.version
        if requirement.specifier and not requirement.specifier.contains(distribution.version, prereleases=True):
            mismatches.append(f"{requirement}: installed {distribution.version}")
        if key in visited:
            continue
        visited.add(key)
        for raw in distribution.requires or []:
            child = Requirement(raw)
            if child.marker is None or any(child.marker.evaluate({"extra": extra}) for extra in ("", *requirement.extras)):
                pending.append(child)
    return {
        "kind": "installed_version_snapshot_not_portable_lock",
        "roots": roots,
        "packages": dict(sorted(versions.items())),
        "missing": sorted(set(missing)),
        "requirement_mismatches": sorted(set(mismatches)),
        "installed_distributions": sorted({canonicalize_name(d.metadata["Name"]): d.version for d in metadata.distributions()}.items()),
    }


def freeze(root: Path, destination: Path) -> dict[str, object]:
    root = root.resolve()
    names = selected_paths(root)
    tracked = set(git(root, "ls-files", "--", *ROOT_FILES, *TREE_RULES).splitlines())
    dependencies = dependency_snapshot(root)
    records = []
    payloads = {}
    for name in names:
        raw = safe_path(root, name).read_bytes()
        payloads[name] = raw
        records.append(
            {
                "path": name,
                "size": len(raw),
                "sha256": digest(raw),
                "tracked": name in tracked,
                "category": "test_source_evidence" if name.startswith("docs/") and name.endswith(".json") else "source_or_documentation",
            }
        )
    source_fingerprint = digest(json.dumps(records, sort_keys=True).encode())
    destination.mkdir(parents=True, exist_ok=False)
    source = destination / "source"
    for name, raw in payloads.items():
        target = safe_path(source, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    # Pin the installed dependency closure for this OS/Python; no direct URLs or credentials.
    pins = "# Observed installed dependency closure; validate in a clean environment.\n"
    pins += "\n".join(f"{name}=={version}" for name, version in dependencies["packages"].items()) + "\n"
    (destination / "requirements-observed.txt").write_text(pins, encoding="utf-8")
    (destination / "environment.json").write_text(json.dumps(dependencies, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(destination / "source.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in payloads.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "git_head": git(root, "rev-parse", "HEAD"),
        "selected_git_status": git(root, "status", "--short", "--untracked-files=all", "--", *names).splitlines(),
        "source_fingerprint": source_fingerprint,
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "in_virtualenv": sys.prefix != sys.base_prefix,
        },
        "selection_rules": {"root_files": ROOT_FILES, "trees": {k: sorted(v) for k, v in TREE_RULES.items()}},
        "excluded": EXCLUSIONS,
        "files": records,
        "artifacts": {
            name: digest((destination / name).read_bytes()) for name in ("source.zip", "environment.json", "requirements-observed.txt")
        },
        "limitations": [
            "Local snapshot contains source evidence fixtures; not a cleared public release.",
            "Corpus, PostgreSQL backup, numeric review history and model weights are excluded.",
            "Clean install, OCR, retrieval and offline acceptance require separate checks.",
        ],
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verify(destination)
    return {
        "destination": str(destination),
        "files": len(records),
        "untracked": sum(not r["tracked"] for r in records),
        "source_fingerprint": source_fingerprint,
        "missing_dependencies": dependencies["missing"],
        "requirement_mismatches": dependencies["requirement_mismatches"],
    }


def verify(destination: Path) -> dict[str, object]:
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    source = destination / "source"
    expected = {r["path"] for r in manifest["files"]}
    actual = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError(f"Source inventory mismatch: extra={sorted(actual - expected)}, missing={sorted(expected - actual)}")
    for record in manifest["files"]:
        raw = safe_path(source, record["path"]).read_bytes()
        if len(raw) != record["size"] or digest(raw) != record["sha256"]:
            raise ValueError(f"Source checksum mismatch: {record['path']}")
    for name, checksum in manifest["artifacts"].items():
        if digest(safe_path(destination, name).read_bytes()) != checksum:
            raise ValueError(f"Artifact checksum mismatch: {name}")
    return {"verified_files": len(expected), "source_fingerprint": manifest["source_fingerprint"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if (args.output is None) == (args.verify is None):
        parser.error("Choose exactly one of --output or --verify")
    result = verify(args.verify) if args.verify is not None else freeze(args.root, args.output)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
