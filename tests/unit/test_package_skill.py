"""
Unit tests for the skill packaging script (scripts/package_skill.py).

Loaded via importlib so this file does not require a `scripts` namespace
package on sys.path.  The script itself also loads test_agent_skill.py by
file path, so no import chain depends on sys.path beyond REPO_ROOT.
"""

from __future__ import annotations

import importlib.util
import shutil
import zipfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load scripts/package_skill.py by file path so the tests do not depend on a
# `scripts` namespace package or any particular sys.path configuration.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "package_skill.py"


def _load_pkg_skill():
    if not _SCRIPT_PATH.is_file():
        raise RuntimeError(
            f"Cannot find packaging script at {_SCRIPT_PATH}. "
            "Run tests from a full repository checkout."
        )
    spec = importlib.util.spec_from_file_location("package_skill", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_pkg = _load_pkg_skill()
SkillValidationError = _pkg.SkillValidationError
compute_sha256 = _pkg.compute_sha256
package_skill = _pkg.package_skill
SECRET_PATTERNS = _pkg.SECRET_PATTERNS

REPO_ROOT = _REPO_ROOT
CANONICAL_SKILL = REPO_ROOT / "skills" / "netcheck-diagnostics"
LICENSE_FILE = REPO_ROOT / "LICENSE"


# ---------------------------------------------------------------------------
# Expected archive entry set computed from the canonical skill folder plus the
# injected LICENSE.  Derived at import time so each test reuses it without
# re-scanning the filesystem.
# ---------------------------------------------------------------------------

def _expected_entries(skill_dir: Path) -> set:
    """Return the exact set of archive names expected for *skill_dir*."""
    top = skill_dir.name
    names = set()
    for fp in skill_dir.rglob("*"):
        if not fp.is_file():
            continue
        if fp.name.startswith(".") or fp.name in {"__pycache__", ".DS_Store"}:
            continue
        if "__pycache__" in fp.parts:
            continue
        rel = fp.relative_to(skill_dir).as_posix()
        names.add(f"{top}/{rel}")
    names.add(f"{top}/LICENSE")
    return names


EXPECTED_CANONICAL_ENTRIES = _expected_entries(CANONICAL_SKILL)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_package_skill_layout(tmp_path: Path):
    """Zip layout: exact entry set, single top-level folder, no double nesting."""
    out_dir = tmp_path / "dist"
    zip_path, sha256 = package_skill(
        skill_dir=CANONICAL_SKILL,
        out_dir=out_dir,
        license_path=LICENSE_FILE,
    )

    assert zip_path.is_file()
    assert sha256 == compute_sha256(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        entry_set = set(zf.namelist())

        # Exact set: no more, no less
        assert entry_set == EXPECTED_CANONICAL_ENTRIES, (
            "Archive entries differ from expected.\n"
            f"  Extra  : {entry_set - EXPECTED_CANONICAL_ENTRIES}\n"
            f"  Missing: {EXPECTED_CANONICAL_ENTRIES - entry_set}"
        )

        # Exactly one top-level folder
        top_levels = {name.split("/")[0] for name in entry_set if name}
        assert top_levels == {"netcheck-diagnostics"}, (
            f"Unexpected top-level folders: {top_levels}"
        )

        # No double nesting
        for name in entry_set:
            assert not name.startswith("netcheck-diagnostics/netcheck-diagnostics/"), (
                f"Double nested entry: {name}"
            )


def test_package_skill_reproducible_sha256(tmp_path: Path):
    """Building twice from the same source produces identical sha256 digests."""
    zip1, sha1 = package_skill(
        skill_dir=CANONICAL_SKILL, out_dir=tmp_path / "build1", license_path=LICENSE_FILE
    )
    zip2, sha2 = package_skill(
        skill_dir=CANONICAL_SKILL, out_dir=tmp_path / "build2", license_path=LICENSE_FILE
    )

    assert sha1 == sha2
    assert zip1.read_bytes() == zip2.read_bytes()


def test_package_skill_zip_entry_metadata(tmp_path: Path):
    """Every ZIP entry must have create_system=3, fixed timestamp, and mode 0o644.

    create_system=3 (Unix) is set explicitly so the archive bytes are identical
    on Windows (default 0) and Linux/macOS (default 3).
    """
    zip_path, _ = package_skill(
        skill_dir=CANONICAL_SKILL, out_dir=tmp_path / "dist", license_path=LICENSE_FILE
    )
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            assert info.create_system == 3, (
                f"{info.filename}: expected create_system=3 (Unix), got {info.create_system}"
            )
            assert info.date_time == (1980, 1, 1, 0, 0, 0), (
                f"{info.filename}: unexpected date_time {info.date_time}"
            )
            mode = (info.external_attr >> 16) & 0o777
            assert mode == 0o644, (
                f"{info.filename}: expected mode 0o644, got 0o{mode:o}"
            )


def test_package_skill_readme_inside_skill_included(tmp_path: Path):
    """A README.md placed *inside* the skill folder must be packed."""
    skill_copy = tmp_path / "netcheck-diagnostics"
    shutil.copytree(CANONICAL_SKILL, skill_copy)

    (skill_copy / "README.md").write_text("# inner readme\n", encoding="utf-8", newline="\n")

    zip_path, _ = package_skill(
        skill_dir=skill_copy, out_dir=tmp_path / "dist", license_path=LICENSE_FILE
    )
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert "netcheck-diagnostics/README.md" in zf.namelist(), (
            "README.md inside the skill folder should be packed"
        )


def test_package_skill_validation_fails_local_path(tmp_path: Path):
    """Validation fails when local machine path or private IP is injected."""
    skill_copy = tmp_path / "netcheck-diagnostics"
    shutil.copytree(CANONICAL_SKILL, skill_copy)

    skill_md = skill_copy / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8") + "\nTarget IP: 192.168.1.100\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(SkillValidationError, match="Local machine paths or private IPs detected"):
        package_skill(skill_dir=skill_copy, out_dir=tmp_path / "dist", license_path=LICENSE_FILE)


def test_package_skill_validation_fails_mismatched_version(tmp_path: Path):
    """Validation fails when expected_version disagrees with SKILL.md metadata.version.

    Passes expected_version="9.9.9" on an *unmodified* skill copy so the test
    is independent of the current version string in SKILL.md.
    """
    skill_copy = tmp_path / "netcheck-diagnostics"
    shutil.copytree(CANONICAL_SKILL, skill_copy)

    with pytest.raises(SkillValidationError, match="does not match expected version"):
        package_skill(
            skill_dir=skill_copy,
            out_dir=tmp_path / "dist",
            license_path=LICENSE_FILE,
            expected_version="9.9.9",
        )


def test_package_skill_validation_fails_mismatched_name(tmp_path: Path):
    """Validation fails when frontmatter name does not match directory name."""
    skill_copy = tmp_path / "netcheck-diagnostics"
    shutil.copytree(CANONICAL_SKILL, skill_copy)

    skill_md = skill_copy / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8").replace(
            "name: netcheck-diagnostics", "name: wrong-skill-name"
        ),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(SkillValidationError, match="does not match directory name"):
        package_skill(skill_dir=skill_copy, out_dir=tmp_path / "dist", license_path=LICENSE_FILE)


def test_package_skill_validation_fails_crlf(tmp_path: Path):
    """Validation fails when CRLF line endings are introduced."""
    skill_copy = tmp_path / "netcheck-diagnostics"
    shutil.copytree(CANONICAL_SKILL, skill_copy)

    skill_md = skill_copy / "SKILL.md"
    skill_md.write_bytes(skill_md.read_bytes().replace(b"\n", b"\r\n"))

    with pytest.raises(SkillValidationError, match="Non-LF line endings detected"):
        package_skill(skill_dir=skill_copy, out_dir=tmp_path / "dist", license_path=LICENSE_FILE)


def test_package_skill_validation_fails_secret(tmp_path: Path):
    """Validation fails when an obvious secret assignment is detected.

    Uses an obviously fake placeholder value (EXAMPLEKEY…) to avoid
    triggering external secret scanners on real credentials.
    SECRET_PATTERNS matches api_key = '...' assignments with >=8 chars.
    """
    # Sanity check: SECRET_PATTERNS catches the fake key before we exercise
    # the full packaging path (ensures the pattern itself is correct).
    fake_line = "api_key = 'EXAMPLEKEY12345678'"
    assert any(p.search(fake_line) for p in SECRET_PATTERNS), (
        "SECRET_PATTERNS should match the fake api_key assignment"
    )

    skill_copy = tmp_path / "netcheck-diagnostics"
    shutil.copytree(CANONICAL_SKILL, skill_copy)

    skill_md = skill_copy / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8") + "\n" + fake_line + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(SkillValidationError, match="Potential secret detected"):
        package_skill(skill_dir=skill_copy, out_dir=tmp_path / "dist", license_path=LICENSE_FILE)


def test_package_skill_validation_fails_binary(tmp_path: Path):
    """Validation fails when binary file is present."""
    skill_copy = tmp_path / "netcheck-diagnostics"
    shutil.copytree(CANONICAL_SKILL, skill_copy)

    (skill_copy / "payload.bin").write_bytes(b"\x00\x01\x02\x03\xff")

    with pytest.raises(SkillValidationError, match="Binary file detected"):
        package_skill(skill_dir=skill_copy, out_dir=tmp_path / "dist", license_path=LICENSE_FILE)


_BUILD_PACKAGES_PATH = _REPO_ROOT / "build_packages.py"


def _load_build_packages():
    spec = importlib.util.spec_from_file_location("build_packages", _BUILD_PACKAGES_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_build_packages = _load_build_packages()


def test_sync_version_skill_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """sync_version propagates the new version to SKILL.md in a mock tree.

    Copies all files touched by sync_version() into a tmp_path tree, monkeypatches
    build_packages.REPO_ROOT, runs sync_version('9.9.9'), and asserts:
    1. metadata.version in SKILL.md becomes '9.9.9' and parses with the frontmatter parser.
    2. The rest of SKILL.md is identical apart from that version line (verified pairwise).
    3. SKILL.md still has no \r (LF endings intact).
    """
    import re

    files_touched = [
        "netcheck/__init__.py",
        "pyproject.toml",
        "netcheck/mcp/server.py",
        "packaging/windows/scoop/netcheck.json",
        "packaging/homebrew/netcheck.rb",
        "packaging/aur/PKGBUILD",
        "skills/netcheck-diagnostics/SKILL.md",
        "packaging/snap/snapcraft.yaml",
    ]
    for rel in files_touched:
        src = REPO_ROOT / rel
        if src.exists():
            dst = tmp_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    skill_md = tmp_path / "skills" / "netcheck-diagnostics" / "SKILL.md"
    orig_text = skill_md.read_text(encoding="utf-8")
    orig_bytes = skill_md.read_bytes()

    orig_version_match = re.search(r'(?m)^  version:\s*"([^"]+)"', orig_text)
    assert orig_version_match is not None, "Could not find metadata.version in SKILL.md"
    orig_version = orig_version_match.group(1)

    monkeypatch.setattr(_build_packages, "REPO_ROOT", tmp_path)
    _build_packages.sync_version("9.9.9")

    updated_text = skill_md.read_text(encoding="utf-8")
    updated_bytes = skill_md.read_bytes()

    # 1. Assert metadata.version in SKILL.md == '9.9.9' via frontmatter parser
    fm = _pkg.parse_frontmatter(updated_text)
    assert "metadata" in fm, "Parsed frontmatter missing 'metadata' section"
    assert fm["metadata"].get("version") == "9.9.9"

    # 2. Assert the rest of SKILL.md is identical apart from that version line
    expected_text = re.sub(
        r'(?m)^  version:\s*"[^"]+"',
        '  version: "9.9.9"',
        orig_text,
    )
    assert updated_text == expected_text

    # Pairwise line comparison: exactly one line differs, and it is metadata.version
    orig_lines = orig_text.splitlines()
    updated_lines = updated_text.splitlines()
    assert len(orig_lines) == len(updated_lines), (
        f"Line count changed: {len(orig_lines)} -> {len(updated_lines)}"
    )
    differing_lines = [
        (i, o, u)
        for i, (o, u) in enumerate(zip(orig_lines, updated_lines), 1)
        if o != u
    ]
    assert len(differing_lines) == 1, (
        f"Expected exactly 1 differing line, found {len(differing_lines)}: {differing_lines}"
    )
    diff_idx, orig_line, updated_line = differing_lines[0]
    assert orig_line == f'  version: "{orig_version}"', (
        f"Differing line at {diff_idx} is not metadata.version: '{orig_line}'"
    )
    assert updated_line == '  version: "9.9.9"', (
        f"Updated line at {diff_idx} is not expected version line: '{updated_line}'"
    )

    # 3. Assert SKILL.md still has no \r (LF endings intact)
    assert b"\r" not in updated_bytes, "sync_version injected CRLF into SKILL.md"
    expected_bytes = orig_bytes.replace(
        f'  version: "{orig_version}"'.encode("utf-8"),
        b'  version: "9.9.9"',
    )
    assert updated_bytes == expected_bytes


def test_sync_version_preserves_line_endings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """sync_version preserves existing line endings: CRLF stays CRLF, LF stays LF."""
    # Setup CRLF file (e.g. netcheck/__init__.py)
    init_py = tmp_path / "netcheck" / "__init__.py"
    init_py.parent.mkdir(parents=True, exist_ok=True)
    with open(init_py, "w", encoding="utf-8", newline="") as f:
        f.write('"""Netcheck init."""\r\n__version__ = "0.0.1"\r\n')

    # Setup LF file (e.g. packaging/aur/PKGBUILD)
    pkgbuild = tmp_path / "packaging" / "aur" / "PKGBUILD"
    pkgbuild.parent.mkdir(parents=True, exist_ok=True)
    with open(pkgbuild, "w", encoding="utf-8", newline="") as f:
        f.write("pkgname=netcheck\npkgver=0.0.1\npkgrel=1\n")

    # Setup LF SKILL.md
    skill_md = tmp_path / "skills" / "netcheck-diagnostics" / "SKILL.md"
    skill_md.parent.mkdir(parents=True, exist_ok=True)
    orig_skill_bytes = (REPO_ROOT / "skills" / "netcheck-diagnostics" / "SKILL.md").read_bytes()
    with open(skill_md, "w", encoding="utf-8", newline="") as f:
        f.write(orig_skill_bytes.decode("utf-8"))

    monkeypatch.setattr(_build_packages, "REPO_ROOT", tmp_path)
    _build_packages.sync_version("9.9.9")

    # CRLF copy must stay CRLF
    init_bytes = init_py.read_bytes()
    assert b"\r\n" in init_bytes
    assert b'__version__ = "9.9.9"\r\n' in init_bytes

    # LF copy must stay LF (no \r anywhere)
    pkgbuild_bytes = pkgbuild.read_bytes()
    assert b"\r" not in pkgbuild_bytes
    assert b"pkgver=9.9.9\n" in pkgbuild_bytes

    # SKILL.md stays LF-only with only its version line changed
    skill_bytes = skill_md.read_bytes()
    assert b"\r" not in skill_bytes
    assert b'  version: "9.9.9"' in skill_bytes


