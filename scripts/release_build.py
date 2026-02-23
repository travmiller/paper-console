#!/usr/bin/env python3
"""
Build versioned production release artifacts for PC-1.

Creates:
1) pc1-<version>.tar.gz     (runtime bundle)
2) pc1-<version>.sha256     (single-file checksum)
3) release-manifest-<version>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "release-artifacts"
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

# Keep release contents explicit and predictable.
INCLUDE_PATHS = [
    "app",
    "icons",
    "scripts",
    "web/dist",
    "requirements.txt",
    "requirements-dev.txt",
    "run.sh",
    "run.bat",
    "AGENTS.md",
    "readme.md",
]

# Exclusions within included directories.
EXCLUDED_DIRS = {".git", ".github", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create PC-1 production release artifacts.")
    parser.add_argument(
        "--version",
        required=True,
        help="Semantic version tag (example: v1.2.3)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for generated artifacts",
    )
    parser.add_argument(
        "--build-web",
        action="store_true",
        help="Run npm ci && npm run build in web/ before packaging",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pytest test gate before packaging",
    )
    return parser.parse_args()


def validate_version(version: str) -> None:
    if not VERSION_RE.match(version):
        raise ValueError(
            f"Invalid version '{version}'. Expected semver tag like v1.2.3 or v1.2.3-rc.1"
        )


def run_command(cmd: list[str], cwd: Path) -> None:
    pretty = " ".join(cmd)
    print(f"[*] {pretty}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def maybe_run_tests(skip_tests: bool) -> None:
    if skip_tests:
        print("[i] Skipping tests (--skip-tests)")
        return

    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if py.exists():
        run_command([str(py), "-m", "pytest", "testing", "-q"], ROOT)
        return

    # WSL/Linux fallback
    run_command(["./.venv/bin/python", "-m", "pytest", "testing", "-q"], ROOT)


def maybe_build_web(build_web: bool) -> None:
    if not build_web:
        return
    run_command(["npm", "ci"], ROOT / "web")
    run_command(["npm", "run", "build"], ROOT / "web")


def copytree_filtered(src: Path, dst: Path) -> None:
    for base, dirs, files in os.walk(src):
        base_path = Path(base)
        rel_base = base_path.relative_to(src)

        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        target_base = dst / rel_base
        target_base.mkdir(parents=True, exist_ok=True)

        for name in files:
            if name.startswith(".env"):
                continue
            file_path = base_path / name
            if file_path.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            shutil.copy2(file_path, target_base / name)


def stage_release_tree(version: str) -> tuple[Path, Path]:
    tmp_dir = Path(tempfile.mkdtemp(prefix="pc1-release-"))
    release_root = tmp_dir / f"pc1-{version}"
    release_root.mkdir(parents=True, exist_ok=True)

    for rel in INCLUDE_PATHS:
        src = ROOT / rel
        if not src.exists():
            raise FileNotFoundError(f"Required release path missing: {rel}")
        dst = release_root / rel
        if src.is_dir():
            copytree_filtered(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # Version marker consumed by production update/version APIs.
    (release_root / ".version").write_text(version + "\n", encoding="utf-8")
    return tmp_dir, release_root


def create_tarball(release_root: Path, output_dir: Path, version: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    tarball_path = output_dir / f"pc1-{version}.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(release_root, arcname=release_root.name)
    return tarball_path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def write_metadata(version: str, tarball_path: Path, output_dir: Path) -> None:
    sha = file_sha256(tarball_path)
    sha_path = output_dir / f"pc1-{version}.sha256"
    sha_path.write_text(f"{sha}  {tarball_path.name}\n", encoding="utf-8")

    manifest = {
        "product": "pc1",
        "version": version,
        "tarball": tarball_path.name,
        "sha256": sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = output_dir / f"release-manifest-{version}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print("\n[OK] Release artifacts created")
    print(f"  - {tarball_path}")
    print(f"  - {sha_path}")
    print(f"  - {manifest_path}")


def main() -> int:
    args = parse_args()
    validate_version(args.version)

    maybe_run_tests(args.skip_tests)
    maybe_build_web(args.build_web)

    tmp_dir = None
    try:
        tmp_dir, release_root = stage_release_tree(args.version)
        tarball_path = create_tarball(release_root, Path(args.output_dir), args.version)
        write_metadata(args.version, tarball_path, Path(args.output_dir))
        return 0
    finally:
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
