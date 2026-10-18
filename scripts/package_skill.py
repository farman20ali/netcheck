#!/usr/bin/env python3
"""
Packaging script for the NetCheck Agent Skill.

Builds a reproducible ZIP package containing the canonical skill:
- Input: skills/netcheck-diagnostics/
- Output: dist/skill/netcheck-diagnostics-<version>.zip
- Top-level archive folder: netcheck-diagnostics/

Stdlib-only: zipfile, hashlib, argparse, pathlib, os, sys, re, importlib.

Reproducibility note
--------------------
ZIP entries are written with:
  - create_system = 3  (Unix attribute convention, regardless of host OS)
  - compress_type = ZIP_STORED  (no zlib; hash is independent of zlib version)
  - external_attr = 0o644 mode
  - fixed date_time (1980-01-01 or SOURCE_DATE_EPOCH)
  - deterministically sorted entry order

Hashes are *expected* to match across OSes. Verified on Windows (Python 3.13)
only; Linux/macOS have not been tested.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import zipfile

# Ensure repository root is on sys.path for netcheck import.
# REPO_ROOT is derived from __file__ so the script works regardless of cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import netcheck  # noqa: E402

# ---------------------------------------------------------------------------
# Load helpers from tests/unit/test_agent_skill.py by file path to avoid a
# hard import-time coupling to the test package.  The script can therefore be
# run from any working directory as long as the repository checkout is intact.
# ---------------------------------------------------------------------------
_HELPER_MODULE_PATH = REPO_ROOT / "tests" / "unit" / "test_agent_skill.py"


def _load_test_helpers():
    """Dynamically load test_agent_skill and return it as a module object.

    Exits with a clear message if the file is missing so the user knows they
    must run the script from a full repository checkout.
    """
    if not _HELPER_MODULE_PATH.is_file():
        sys.exit(
            f"ERROR: helper module not found at {_HELPER_MODULE_PATH}\n"
            "Run scripts/package_skill.py from a full repository checkout."
        )
    spec = importlib.util.spec_from_file_location("test_agent_skill", _HELPER_MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_helpers = _load_test_helpers()
find_local_paths = _helpers.find_local_paths
parse_frontmatter = _helpers.parse_frontmatter


class SkillValidationError(Exception):
    """Raised when skill validation fails prior to packaging."""


SECRET_PATTERNS = [
    re.compile(
        r"""(?i)\b(?:api[_-]?key|auth[_-]?token|access[_-]?token|secret[_-]?key|password)\s*[:=]\s*['"][a-zA-Z0-9_\-./+=]{8,}['"]"""
    ),
    re.compile(r"""(?i)\b(?:bearer\s+[a-zA-Z0-9_\-\.]{16,})"""),
    re.compile(r"""-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"""),
]

IGNORED_NAMES = {".DS_Store", "__pycache__"}


def is_binary_file(path: Path) -> bool:
    """Return True if *path* contains binary content (null bytes or non-UTF-8)."""
    try:
        raw = path.read_bytes()
        if b"\x00" in raw:
            return True
        raw.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def validate_skill_source(skill_dir: Path, expected_version: str | None = None) -> None:
    """Validate skill folder before packaging.

    Checks:
    1. SKILL.md exists and frontmatter name matches directory name.
    2. Frontmatter metadata.version matches netcheck.__version__.
    3. All files are UTF-8 text (reject binaries).
    4. No CRLF or CR line endings (LF only).
    5. No local-machine paths or private IPs.
    6. No obvious secrets (api key, token, password assignments).
    """
    if expected_version is None:
        expected_version = netcheck.__version__

    if not skill_dir.is_dir():
        raise SkillValidationError(f"Skill directory does not exist: {skill_dir}")

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise SkillValidationError(f"Missing required SKILL.md at {skill_md}")

    # 1 & 2: Frontmatter validation
    content = skill_md.read_text(encoding="utf-8")
    try:
        fm = parse_frontmatter(content)
    except Exception as exc:
        raise SkillValidationError(f"Failed to parse SKILL.md frontmatter: {exc}") from exc

    fm_name = fm.get("name")
    if fm_name != skill_dir.name:
        raise SkillValidationError(
            f"Frontmatter name '{fm_name}' does not match directory name '{skill_dir.name}'"
        )

    meta = fm.get("metadata", {})
    fm_version = meta.get("version") if isinstance(meta, dict) else None
    if fm_version != expected_version:
        raise SkillValidationError(
            f"Frontmatter metadata.version '{fm_version}' does not match expected version"
            f" '{expected_version}'"
        )

    # 3-6: Validate all files in skill_dir
    for item in sorted(skill_dir.rglob("*")):
        if (
            item.name.startswith(".")
            or item.name in IGNORED_NAMES
            or "__pycache__" in item.parts
        ):
            continue
        if not item.is_file():
            continue

        # 3: Reject binaries
        if is_binary_file(item):
            raise SkillValidationError(f"Binary file detected (only text allowed): {item}")

        # 4: LF line endings only
        raw_bytes = item.read_bytes()
        if b"\r\n" in raw_bytes or b"\r" in raw_bytes:
            raise SkillValidationError(f"Non-LF line endings detected in: {item}")

        # 5: No local machine paths / private IPs
        text = raw_bytes.decode("utf-8")
        local_hits = find_local_paths(text)
        if local_hits:
            details = ", ".join(f"line {no}: {pat}" for no, _, pat in local_hits[:3])
            raise SkillValidationError(
                f"Local machine paths or private IPs detected in {item.name}: {details}"
            )

        # 6: No obvious secrets
        for line_no, line in enumerate(text.splitlines(), 1):
            for pat in SECRET_PATTERNS:
                if pat.search(line):
                    raise SkillValidationError(
                        f"Potential secret detected in {item.name} at line {line_no}"
                    )


def compute_sha256(file_path: Path) -> str:
    """Return the SHA-256 hex digest of *file_path*."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def get_fixed_zip_time() -> tuple:
    """Return a reproducible ZIP date_time tuple (1980-01-01 or SOURCE_DATE_EPOCH)."""
    epoch_str = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch_str:
        dt = datetime.datetime.fromtimestamp(int(epoch_str), tz=datetime.timezone.utc)
        return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    return (1980, 1, 1, 0, 0, 0)


def package_skill(
    skill_dir: Path,
    out_dir: Path,
    license_path: Path | None = None,
    expected_version: str | None = None,
) -> tuple:
    """Build a reproducible ZIP for the skill.  Returns (zip_path, sha256).

    Reproducibility: entries use create_system=3 (Unix), ZIP_STORED, mode
    0o644, and a fixed timestamp.  The sha256 is expected to be identical
    across OSes and Python versions.  Verified on Windows only.
    """
    if expected_version is None:
        expected_version = netcheck.__version__

    if license_path is None:
        license_path = REPO_ROOT / "LICENSE"

    if not license_path.is_file():
        raise SkillValidationError(f"LICENSE file not found at: {license_path}")

    validate_skill_source(skill_dir, expected_version=expected_version)

    out_dir.mkdir(parents=True, exist_ok=True)
    zip_filename = f"netcheck-diagnostics-{expected_version}.zip"
    zip_path = out_dir / zip_filename

    fixed_time = get_fixed_zip_time()
    top_folder = skill_dir.name  # "netcheck-diagnostics"

    # Collect (archive_name, bytes) for every file inside skill_dir, excluding
    # dotfiles and ignored names.  Files outside skill_dir (e.g. skills/README.md)
    # are never included because we only iterate inside skill_dir.
    entries: list = []
    for file_path in sorted(skill_dir.rglob("*")):
        if not file_path.is_file():
            continue
        if (
            file_path.name.startswith(".")
            or file_path.name in IGNORED_NAMES
            or "__pycache__" in file_path.parts
        ):
            continue
        rel = file_path.relative_to(skill_dir)
        arcname = f"{top_folder}/{rel.as_posix()}"
        entries.append((arcname, file_path.read_bytes()))

    # LICENSE from repo root, normalised to LF
    license_bytes = (
        license_path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
    )
    entries.append((f"{top_folder}/LICENSE", license_bytes))

    # Deterministic order
    entries.sort(key=lambda t: t[0])

    # Build the zip.
    #   create_system = 3  (Unix) must be set explicitly; the default differs
    #     between Windows (0) and Linux (3), which would change the zip bytes.
    #   ZIP_STORED avoids dependency on the zlib version.
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        for arcname, data in entries:
            zinfo = zipfile.ZipInfo(filename=arcname, date_time=fixed_time)
            zinfo.compress_type = zipfile.ZIP_STORED
            zinfo.create_system = 3  # Unix — set explicitly for cross-OS reproducibility
            zinfo.external_attr = (0o644 | 0o100000) << 16
            zf.writestr(zinfo, data)

    sha256 = compute_sha256(zip_path)
    return zip_path, sha256


def list_zip_contents(zip_path: Path) -> None:
    """Print the archive path, sha256, and entry listing."""
    sha256 = compute_sha256(zip_path)
    print(f"Archive: {zip_path}")
    print(f"SHA256:  {sha256}")
    print("\nEntries:")
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            print(f"  {info.file_size:8d}  {info.date_time}  {info.filename}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Package NetCheck Agent Skill into a reproducible ZIP."
    )
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=REPO_ROOT / "skills" / "netcheck-diagnostics",
        help="Path to canonical skill directory (default: skills/netcheck-diagnostics)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "dist" / "skill",
        help="Output directory (default: dist/skill)",
    )
    parser.add_argument(
        "--license",
        type=Path,
        default=REPO_ROOT / "LICENSE",
        help="Path to repository LICENSE file (default: LICENSE)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List entries of the resulting zip and sha256 checksum",
    )
    args = parser.parse_args()

    try:
        zip_path, sha256 = package_skill(
            skill_dir=args.skill_dir,
            out_dir=args.out,
            license_path=args.license,
        )
    except SkillValidationError as exc:
        sys.stderr.write(f"Validation Error: {exc}\n")
        sys.exit(1)
    except Exception as exc:
        sys.stderr.write(f"Packaging failed: {exc}\n")
        sys.exit(2)

    print(f"Skill successfully packaged to: {zip_path}")
    print(f"SHA256: {sha256}")

    if args.list:
        print()
        list_zip_contents(zip_path)


if __name__ == "__main__":
    main()