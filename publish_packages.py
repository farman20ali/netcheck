#!/usr/bin/env python3
"""
publish_packages.py — netcheck publish orchestrator
====================================================
Mirrors the flag-based interface of build_packages.py but for *publishing*
already-built artefacts to public stores.

Usage examples
--------------
  python3 publish_packages.py --check                     # verify all publish tools
  python3 publish_packages.py --pypi                      # upload to PyPI (production)
  python3 publish_packages.py --pypi --test               # upload to TestPyPI first
  python3 publish_packages.py --snap                      # push to Snap Store (stable)
  python3 publish_packages.py --snap --channel edge       # push to edge/beta/candidate
  python3 publish_packages.py --chocolatey                # push nupkg to Chocolatey.org
  python3 publish_packages.py --winget                    # submit/update package in WinGet
  python3 publish_packages.py --winget --version 2.5.0    # specify version explicitly

Environment variables (optional, avoids interactive prompts)
------------------------------------------------------------
  TWINE_USERNAME / TWINE_PASSWORD   — PyPI credentials (or __token__ / API key)
  SNAPCRAFT_STORE_CREDENTIALS       — Snapcraft exported credentials
  CHOCO_API_KEY                     — Chocolatey.org API key
  WINGET_GITHUB_TOKEN / GH_TOKEN    — GitHub PAT for WinGet PR submission
"""

import argparse
import os
import platform
import re
import subprocess
import sys

# Force stdout and stderr to UTF-8 to prevent UnicodeEncodeError on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, TypeError):
    pass
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.resolve()
DIST_DIR  = REPO_ROOT / "dist"

# ── Python executable (platform-aware) ───────────────────────────────────────
PYTHON_CMD = "python" if platform.system().lower() == "windows" else "python3"


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_version() -> str:
    """Return the current netcheck version string from __init__.py."""
    init = REPO_ROOT / "netcheck" / "__init__.py"
    m = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]', init.read_text(encoding="utf-8"))
    if not m:
        sys.exit("Error: cannot parse __version__ from netcheck/__init__.py")
    return m.group(1)


def _tool_ok(name: str) -> bool:
    """Return True if *name* is findable on PATH."""
    return subprocess.run(
        ["which", name] if os.name != "nt" else ["where", name],
        capture_output=True
    ).returncode == 0


def _run(cmd: list, label: str) -> None:
    """Run *cmd*, print output live, and abort on non-zero exit."""
    sep = "─" * 60
    print(f"\n{sep}\n▶ {label}\n$ {' '.join(cmd)}\n{sep}")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        sys.exit(f"\n❌  {label} failed (exit {result.returncode})")
    print(f"✅  {label}")


def _glob_newest(pattern: str, sub: str = "") -> Path | None:
    """Return the newest file matching *pattern* inside dist/[sub]."""
    search_dir = DIST_DIR / sub if sub else DIST_DIR
    matches = sorted(search_dir.glob(pattern))
    return matches[-1] if matches else None


# ── --check ───────────────────────────────────────────────────────────────────

def run_check() -> None:
    """Print availability of all publish-time tools."""
    print("\n─── Publish tool diagnostic ───\n")
    tools = {
        "twine"       : "pip install twine",
        "snapcraft"   : "sudo snap install snapcraft --classic",
        "choco"       : "https://chocolatey.org/install  (Windows only)",
        "wingetcreate": "winget install Microsoft.WingetCreate  (Windows only)",
        "gh"          : "https://cli.github.com  (optional, for GitHub Releases)",
    }
    all_ok = True
    for tool, install_hint in tools.items():
        ok  = _tool_ok(tool)
        sym = "✅" if ok else "❌"
        hint = "" if ok else f"  →  {install_hint}"
        print(f"  {sym}  {tool:<14}{hint}")
        if not ok:
            all_ok = False
    print()
    if all_ok:
        print("✅  All publish tools are available.")
    else:
        print("⚠️   Install the missing tools before publishing.")


# ── --pypi ────────────────────────────────────────────────────────────────────

def publish_pypi(test: bool = False) -> None:
    """Upload wheel + sdist to PyPI (or TestPyPI when *test* is True)."""
    print(f"\n─── Publishing to {'TestPyPI' if test else 'PyPI'} ───")

    if not _tool_ok("twine"):
        sys.exit("❌  twine not found.\n  Install: pip install twine")

    # Collect artefacts
    artefacts = list(DIST_DIR.glob("netcheckx-*.whl")) + list(DIST_DIR.glob("netcheckx-*.tar.gz"))
    if not artefacts:
        sys.exit(
            "❌  No wheel / sdist found in dist/.\n"
            f"  Run first:  {PYTHON_CMD} build_packages.py --pypi"
        )

    print("  Artefacts to upload:")
    for a in sorted(artefacts):
        print(f"    {a.name}")

    cmd = ["twine", "upload"]
    if test:
        cmd += ["--repository", "testpypi"]
    cmd += [str(a) for a in sorted(artefacts)]

    _run(cmd, f"twine upload → {'TestPyPI' if test else 'PyPI'}")
    store_url = "https://test.pypi.org/project/netcheckx/" if test else "https://pypi.org/project/netcheckx/"
    print(f"\n🔗  View at: {store_url}")


# ── --snap ────────────────────────────────────────────────────────────────────

def publish_snap(channel: str = "stable") -> None:
    """Upload the newest .snap to the Snap Store and release to *channel*."""
    print(f"\n─── Publishing to Snap Store (channel: {channel}) ───")

    if not _tool_ok("snapcraft"):
        sys.exit("❌  snapcraft not found.\n  Install: sudo snap install snapcraft --classic")

    snap_file = _glob_newest("*.snap", sub="snap")
    if snap_file is None:
        # Also check root-level snaps (leftover from older builds)
        snap_file = _glob_newest("netcheck_*.snap")
    if snap_file is None:
        sys.exit(
            "❌  No .snap file found in dist/snap/ or repo root.\n"
            f"  Run first:  {PYTHON_CMD} build_packages.py --snap"
        )

    print(f"  Snap file: {snap_file.name}")

    # Upload — snapcraft upload returns the revision number
    print(f"\n  Uploading {snap_file.name} …")
    upload_result = subprocess.run(
        ["snapcraft", "upload", str(snap_file), "--release", channel],
        cwd=REPO_ROOT,
        capture_output=False,
    )
    if upload_result.returncode != 0:
        sys.exit("❌  snapcraft upload failed.")

    print(f"\n✅  Snap published to channel '{channel}'.")
    print("🔗  View at: https://snapcraft.io/netcheck")

    # Show current channel status
    print()
    subprocess.run(["snapcraft", "status", "netcheck"], cwd=REPO_ROOT)


# ── --chocolatey ──────────────────────────────────────────────────────────────

def publish_chocolatey(checksum_val: str | None = None, checksum_from_release: bool = False, checksum_file: str | None = None) -> None:
    """Push the newest .nupkg to Chocolatey.org."""
    print("\n─── Publishing to Chocolatey ───")

    if not _tool_ok("choco"):
        sys.exit(
            "❌  choco not found. Chocolatey is Windows-only.\n"
            "  Install: https://chocolatey.org/install"
        )

    # Determine if rebuilding is needed or prompt if interactive and no options provided
    rebuild = bool(checksum_val or checksum_from_release or checksum_file)

    if not rebuild and sys.stdin.isatty():
        print("\n--- Chocolatey Package Publish Options ---")
        print("Choose an action:")
        print("  [1] Push the existing package as-is (default)")
        print("  [2] Rebuild package using live GitHub release checksum")
        print("  [3] Rebuild package using manual checksum entry")
        print("  [4] Rebuild package using custom file")
        print("  [5] Rebuild package using local installer file")

        try:
            choice = input("Enter choice [1-5] (default 1): ").strip()
        except KeyboardInterrupt:
            sys.exit("\nAborted.")

        if choice == "2":
            checksum_from_release = True
            rebuild = True
        elif choice == "3":
            val = input("Enter SHA-256 checksum (64-char hex): ").strip()
            if re.match(r"^[0-9a-fA-F]{64}$", val):
                checksum_val = val
                rebuild = True
            else:
                print("⚠️   Invalid SHA-256 format. Proceeding with existing package.")
        elif choice == "4":
            path_str = input("Enter file path: ").strip()
            if path_str:
                checksum_file = path_str
                rebuild = True
            else:
                print("⚠️   No path entered. Proceeding with existing package.")
        elif choice == "5":
            rebuild = True

    if rebuild:
        print("  Rebuilding Chocolatey package before publishing...")
        cmd = [PYTHON_CMD, "build_packages.py", "--choco"]
        if checksum_val:
            cmd += ["--choco-checksum", checksum_val]
        if checksum_from_release:
            cmd += ["--choco-checksum-from-release"]
        if checksum_file:
            cmd += ["--choco-checksum-file", checksum_file]

        _run(cmd, "Rebuilding Chocolatey package")

    nupkg = _glob_newest("netcheck.*.nupkg", sub="choco")
    if nupkg is None:
        sys.exit(
            "❌  No .nupkg found in dist/choco/.\n"
            f"  Run first:  {PYTHON_CMD} build_packages.py --win"
        )

    print(f"  Package: {nupkg.name}")

    api_key = os.environ.get("CHOCO_API_KEY", "")
    cmd = ["choco", "push", str(nupkg), "--source", "https://push.chocolatey.org/"]
    if api_key:
        cmd += ["--api-key", api_key]
    else:
        print("  ℹ️   CHOCO_API_KEY not set — you will be prompted for it.")
        print("\n*********** powershell ************ \n either run command--> $env:CHOCO_API_KEY=\"YOUR_CHOCOLATEY_API_KEY\" \n or \n run command for user permanantly-->  [System.Environment]::SetEnvironmentVariable('CHOCO_API_KEY', 'YOUR_CHOCOLATEY_API_KEY', 'User')")
        print("\n ************cmd *********** \n run command --> set CHOCO_API_KEY=YOUR_CHOCOLATEY_API_KEY")
    _run(cmd, "choco push → Chocolatey.org")
    print("🔗  View at: https://community.chocolatey.org/packages/netcheck")


# ── --github-release (optional helper) ───────────────────────────────────────

def publish_github_release(tag: str) -> None:
    """Create a GitHub release for *tag* and attach all dist artefacts."""
    print(f"\n─── Creating GitHub Release {tag} ───")

    if not _tool_ok("gh"):
        sys.exit(
            "❌  gh (GitHub CLI) not found.\n"
            "  Install: https://cli.github.com"
        )

    # Collect all dist artefacts (wheel, sdist, deb, snap, nupkg)
    artefacts: list[Path] = []
    artefacts += list(DIST_DIR.glob("*.whl"))
    artefacts += list(DIST_DIR.glob("*.tar.gz"))
    artefacts += list((DIST_DIR / "deb").glob("*.deb"))
    artefacts += list((DIST_DIR / "snap").glob("*.snap"))
    artefacts += list((DIST_DIR / "choco").glob("*.nupkg"))

    if not artefacts:
        sys.exit("❌  No artefacts found in dist/. Build them first.")

    notes_path = REPO_ROOT / "docs" / "releases" / f"RELEASE_NOTES_V{tag.lstrip('v').replace('.', '.')}.md"
    notes_flag = ["--notes-file", str(notes_path)] if notes_path.exists() else ["--generate-notes"]

    cmd = (
        ["gh", "release", "create", tag,
         "--title", f"netcheck {tag}",
         "--latest"]
        + notes_flag
        + [str(a) for a in sorted(artefacts)]
    )
    _run(cmd, f"gh release create {tag}")
    print(f"🔗  https://github.com/farman20ali/netcheck/releases/tag/{tag}")


# ── --winget ──────────────────────────────────────────────────────────────────

def publish_winget(
    version: str | None = None,
    urls: str | None = None,
    submit: bool = True,
    token: str | None = None,
    yes: bool = False,
) -> None:
    """Submit / update package in Windows Package Manager via wingetcreate."""
    print("\n─── Publishing to WinGet (Windows Package Manager) ───")

    if not _tool_ok("wingetcreate"):
        sys.exit(
            "❌  wingetcreate not found.\n"
            "  Install via winget: winget install Microsoft.WingetCreate\n"
            "  Or download from: https://github.com/microsoft/winget-create/releases"
        )

    ver = version or get_version()
    package_id = "farman20ali.netcheck"
    setup_url = urls or f"https://github.com/farman20ali/netcheck/releases/download/v{ver}/netcheck-{ver}-setup.exe"
    auth_token = token or os.environ.get("WINGET_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    # 1. Token Check and Guidance
    if not auth_token:
        print("\n" + "═" * 60)
        print("⚠️   WINGET_GITHUB_TOKEN not found!")
        print("═" * 60)
        print("""To submit a manifest PR directly to microsoft/winget-pkgs, wingetcreate
needs a GitHub Personal Access Token (PAT) with 'public_repo' permissions.

How to get a token:
  1. Open: https://github.com/settings/tokens/new
  2. Note: "winget submission token"
  3. Scope: Check 'public_repo'
  4. Generate and copy your token (starts with ghp_...)
  (Tip: If you have GitHub CLI authenticated, you can get it via: gh auth token)

How to set your token:
  [PowerShell - Current Session]:
    $env:WINGET_GITHUB_TOKEN = "ghp_your_token_here"

  [PowerShell - Permanent for User]:
    [System.Environment]::SetEnvironmentVariable('WINGET_GITHUB_TOKEN', 'ghp_your_token_here', 'User')

  [CMD - Current Session]:
    set WINGET_GITHUB_TOKEN=ghp_your_token_here

  [CLI Argument]:
    python publish_packages.py --winget --winget-token "ghp_your_token_here"
""")
        print("═" * 60)

        if sys.stdin.isatty() and not yes:
            print("Choose an option:")
            print("  [1] Enter token right now in prompt")
            print("  [2] Continue without token (wingetcreate will use cached auth or browser prompt)")
            print("  [3] Abort now (set token and rerun)")
            try:
                choice = input("Enter choice [1-3] (default 2): ").strip()
            except KeyboardInterrupt:
                sys.exit("\nAborted.")

            if choice == "1":
                try:
                    entered = input("Paste your GitHub Token: ").strip()
                    if entered:
                        auth_token = entered
                    else:
                        print("No token entered. Continuing without token.")
                except KeyboardInterrupt:
                    sys.exit("\nAborted.")
            elif choice == "3":
                sys.exit("Aborted. Please set WINGET_GITHUB_TOKEN and run again.")

    # 2. Pre-execution Review
    token_display = "None (Interactive/Browser fallback)"
    if auth_token:
        if len(auth_token) > 8:
            token_display = f"Configured ({auth_token[:4]}...{auth_token[-4:]})"
        else:
            token_display = "Configured"

    print("\n" + "─" * 60)
    print("WinGet Submission Review")
    print("─" * 60)
    print(f"  Package ID   : {package_id}")
    print(f"  Version      : {ver}")
    print(f"  Installer URL: {setup_url}")
    print(f"  Submit Mode  : {'--submit (Fork and open PR)' if submit else 'Manifest Generation Only (no submit)'}")
    print(f"  GitHub Token : {token_display}")
    print("─" * 60)

    # 3. Confirmation Prompt
    if not yes:
        try:
            confirm = input(f"\nAre you sure you want to proceed with WinGet v{ver}? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            sys.exit("\nAborted.")

        if confirm not in ("y", "yes"):
            print("\n❌  Submission cancelled by user.")
            print("💡  If the version was incorrect, specify: python publish_packages.py --winget --winget-version <version>")
            return

    # 4. Execute wingetcreate
    cmd = ["wingetcreate", "update", package_id, "--version", ver, "--urls", setup_url]
    if submit:
        cmd.append("--submit")
    if auth_token:
        cmd.extend(["--token", auth_token])

    sep = "─" * 60
    print(f"\n{sep}\n▶ wingetcreate update → {package_id} v{ver}\n$ {' '.join(cmd)}\n{sep}")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"\n❌  wingetcreate update failed (exit {result.returncode})")
        print("\nℹ️   Common causes & solutions:")
        print("  1. If this is the FIRST time publishing farman20ali.netcheck:")
        print("     'wingetcreate update' only works after the package has been accepted and merged into microsoft/winget-pkgs.")
        print("     For initial publication, submit the base manifest folder:")
        print("       wingetcreate submit packaging/winget/manifests/f/farman20ali/netcheck/2.4.0 --token <token>")
        print("     (See packaging/winget/README.md for initial submission details)")
        print(f"  2. If the release installer is not accessible on GitHub Releases:")
        print(f"     Verify that {setup_url} is live and downloadable.")
        print("  3. Token permissions:")
        print("     Ensure your GitHub Personal Access Token has the 'public_repo' scope.")
        sys.exit(1)

    print(f"\n✅  WinGet manifest submission complete for {package_id} v{ver}.")
    print("🔗  Track pull requests at: https://github.com/microsoft/winget-pkgs/pulls")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="netcheck publish orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            f"  {PYTHON_CMD} publish_packages.py --check\n"
            f"  {PYTHON_CMD} publish_packages.py --pypi --test\n"
            f"  {PYTHON_CMD} publish_packages.py --pypi\n"
            f"  {PYTHON_CMD} publish_packages.py --snap\n"
            f"  {PYTHON_CMD} publish_packages.py --snap --channel edge\n"
            f"  {PYTHON_CMD} publish_packages.py --chocolatey\n"
            f"  {PYTHON_CMD} publish_packages.py --winget\n"
            f"  {PYTHON_CMD} publish_packages.py --winget --version 2.5.0\n"
            f"  {PYTHON_CMD} publish_packages.py --github-release v2.1.0\n"
        )
    )

    p.add_argument("-y", "--yes",        action="store_true",
                   help="Skip interactive confirmation prompts and proceed automatically")
    p.add_argument("--check",            action="store_true",
                   help="Verify all publish tools are installed")
    p.add_argument("--pypi",             action="store_true",
                   help="Upload wheel + sdist to PyPI")
    p.add_argument("--test",             action="store_true",
                   help="(With --pypi) upload to TestPyPI instead of production")
    p.add_argument("--snap",             action="store_true",
                   help="Upload .snap to Snap Store")
    p.add_argument("--channel",          default="stable", metavar="CHANNEL",
                   help="Snap channel to release to: stable|candidate|beta|edge  (default: stable)")
    p.add_argument("--chocolatey",       action="store_true",
                   help="Push .nupkg to Chocolatey.org")
    p.add_argument("--choco-checksum",                     help="Specify the SHA-256 checksum for the Chocolatey installer manually")
    p.add_argument("--choco-checksum-from-release", action="store_true", help="Download the setup installer from the GitHub release to calculate checksum")
    p.add_argument("--choco-checksum-file",                help="Read the SHA-256 checksum from a file (or calculate the checksum of that file)")
    p.add_argument("--winget",           action="store_true",
                   help="Submit / update package manifest on WinGet via wingetcreate")
    p.add_argument("--winget-version",   metavar="VERSION",
                   help="Version for WinGet update (defaults to current netcheck version)")
    p.add_argument("--winget-url",       metavar="URL",
                   help="Custom setup installer download URL for WinGet")
    p.add_argument("--winget-token",     metavar="TOKEN",
                   help="GitHub Personal Access Token for WinGet PR submission")
    p.add_argument("--no-submit",        action="store_true",
                   help="(With --winget) generate and validate manifest without submitting PR")
    p.add_argument("--github-release",   metavar="TAG",
                   help="Create a GitHub Release for TAG and attach all dist artefacts")

    args = p.parse_args()

    if args.check:
        run_check()
    elif args.pypi:
        publish_pypi(test=args.test)
    elif args.snap:
        publish_snap(channel=args.channel)
    elif args.chocolatey:
        publish_chocolatey(
            checksum_val=args.choco_checksum,
            checksum_from_release=args.choco_checksum_from_release,
            checksum_file=args.choco_checksum_file
        )
    elif args.winget:
        publish_winget(
            version=args.winget_version,
            urls=args.winget_url,
            submit=not args.no_submit,
            token=args.winget_token,
            yes=args.yes,
        )
    elif args.github_release:
        publish_github_release(tag=args.github_release)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
