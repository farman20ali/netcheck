# Release Notes — NetCheck v2.5.0

**Release Date:** 2026-10-10
**Type:** Maintenance — CI Reliability, Repository Rename, Bug Fixes & Test Hardening

---

## Overview

v2.5.0 is a maintenance, resilience, and stability release. It completes the repository rename from
`network_access_check` to `netcheck` across every packaging pipeline, introduces comprehensive
graceful shutdown handling for `Ctrl+C` (SIGINT) across all single, concurrent, and watch checks,
standardises POSIX exit codes (introducing `EXIT_INTERRUPT = 130`), synchronises JSON/CSV/XML output
engines for UDP and MTR checks, hardens the CI matrix by migrating the lint step from `flake8` to `ruff`,
fixes Python 3.8/3.9 test runner syntax compatibility, and resolves timer-jitter race conditions in the cache TTL test suite.

No breaking API or CLI syntax changes. All existing commands, flags, and config formats remain
fully backward-compatible.

---

## What's New

### 1. Repository Rename Completion (`network_access_check` → `netcheck`)

All references to the old repository name have been purged from the codebase and CI pipelines:

- **`.github/workflows/release.yml`** — Winget publish step corrected:
  - Fixed stray `netcheck` token that caused a **PowerShell syntax error** in `$VERSION`
    assignment.
  - Updated GitHub Releases download URL from
    `farman20ali/network_access_check/releases/...` to
    `farman20ali/netcheck/releases/...`.

> GitHub automatically redirects existing repository clones and web links — no action
> needed for existing users.

---

### 2. CI Lint Step: `flake8` → `ruff`

The CI workflow (`ci.yml`) was failing on all runners with:

```
/bin/sh: flake8: command not found
Error: Process completed with exit code 127
```

**Root cause:** `flake8` was never in `[project.optional-dependencies] dev`, so
`pip install .[dev]` did not install it.

**Fix:** Replaced both `flake8` commands with a single `ruff check netcheck` step.
`ruff` is already a dev dependency and is configured in `pyproject.toml` with
equivalent rule sets (`E`, `W`, `F`, `I`).

Additional ruff findings fixed at the same time:
- `netcheck/post_install.py` — unsorted `__future__` import block (`I001`).
- `netcheck/cli/main.py` — invalid `# noqa: unreachable` directive (not a
  recognized rule code) converted to a plain comment.
- `netcheck/cli/subcommands.py` — removed unused `global _metrics_registry`
  declaration (`F824`) from `_record_results_and_check_alerts`; the variable is
  only read there — the actual assignment lives in `_run_serve`.

---

### 3. Python 3.8 / 3.9 Test Compatibility

`tests/unit/test_mtr.py` and `tests/unit/test_udp.py` used parenthesized
context-manager syntax introduced in **Python 3.10** (PEP 617):

```python
# Python 3.10+ ONLY — crashed with SyntaxError on 3.8 and 3.9
with (
    patch("...") as mock_a,
    patch("...") as mock_b,
):
    ...
```

Both files were rewritten to use nested `with` statements, which are valid on
all supported Python versions (3.8–3.12):

```python
with patch("...") as mock_a:
    with patch("...") as mock_b:
        ...
```

---

### 4. Cache TTL Overwrite Race Fix + Test Hardening

**Bug:** `tests/unit/test_cache.py::TestCacheTTL::test_overwrite_resets_ttl`
failed intermittently on macOS CI runners.

**Root cause (implementation):** `Cache.set()` computed `expiry` with
`time.time()` *before* acquiring the lock, then called `time.time()` again
inside the lock for the expired-key cleanup pass. On a slow runner these two
calls could be far enough apart that the key being overwritten appeared expired
during cleanup and was evicted before the new value was stored.

**Fix in `netcheck/utils/cache.py`:**
- Compute `expiry` inside the lock using a single `time.time()` call.
- Exclude the key currently being written from the expired-key cleanup loop
  (`k != key`) to prevent any self-eviction race.

**Root cause (test):** Even with the implementation fixed, `time.sleep(0.03)`
on a loaded macOS runner can sleep for 0.07–0.10 s. With a TTL of 0.05 s, two
back-to-back sleeps easily exceed the new expiry window.

**Fix in `tests/unit/test_cache.py`:**
- All timing-sensitive tests now patch `netcheck.utils.cache.time` and advance
  `time.time()` return values programmatically — zero actual sleeping.
- Tests complete in < 0.1 s and are fully deterministic on any runner.
- Two additional edge-case tests added:
  - `test_overwrite_expired_key_resets_ttl` — overwriting an already-expired
    key still gives the new value a fresh TTL.
  - `test_overwrite_does_not_count_as_new_entry` — overwriting an existing key
    never triggers eviction of other cached entries.

---

### 5. Graceful Ctrl+C (KeyboardInterrupt) & Immediate Shutdown

**Problem:** Pressing `Ctrl+C` while checks (such as DNS resolution, multi-target TCP checks, or port scans) were in progress displayed an unhandled `KeyboardInterrupt` traceback dump and often caused the terminal to hang while worker threads completed blocking network sockets.

**Fix:**
- Added top-level signal & `KeyboardInterrupt` guards in `netcheck.cli.main:main` and `netcheck.cli.subcommands:handle_subcommands`.
- Pending futures in `ThreadPoolExecutor` are cancelled immediately on `KeyboardInterrupt` across batch executor, port scanner, and interface resolution.
- Standard POSIX `130` (`128 + SIGINT`) exit code is returned consistently.
- Interrupt message is written exclusively to `sys.stderr`, preserving clean stdout for pipeline tools (`jq`, grep).

---

### 6. Exit Codes Contract (`EXIT_INTERRUPT = 130`)

Added `EXIT_INTERRUPT = 130` to `netcheck/cli/exitcodes.py` to complement existing codes:
- `EXIT_OK = 0` (All checks passed)
- `EXIT_FAIL = 1` (Target unreachable / network check failure)
- `EXIT_BAD_ARGS = 2` (Invalid argument / empty targets)
- `EXIT_ERROR = 3` (Runtime error)
- `EXIT_INTERRUPT = 130` (Cancelled via SIGINT / Ctrl+C)

Batch targets parsing now returns `EXIT_BAD_ARGS` (2) when given an empty or malformed input file instead of generic failure.

---

### 7. Formatter Parity: UDP & MTR in JSON, CSV, and XML

v2.5.0 introduced UDP probe and MTR hops diagnostic engines. Their dispatch was missing from JSON, CSV, and XML format engines, causing `-f json` to fall back to generic TCP batch schemas.
- Dedicated `_fmt_udp` and `_fmt_mtr` handlers added across `json_fmt.py`, `csv_fmt.py`, and `xml_fmt.py`.
- Full parity between `text`, `json`, `csv`, and `xml` representations.
- Unit tests added to verify formatting accuracy.

---

## Breaking Changes

None.

---

## Files Changed

| File | Change |
|------|--------|
| `netcheck/__init__.py` | Version bumped to `2.5.0` |
| `pyproject.toml` | Version bumped to `2.5.0` |
| `netcheck/cli/exitcodes.py` | Added `EXIT_INTERRUPT = 130` |
| `netcheck/cli/main.py` | Top-level guarded `main()` entrypoint, SIGPIPE handler, graceful Ctrl+C handling |
| `netcheck/cli/subcommands.py` | Added `KeyboardInterrupt` handler and exit code propagation |
| `netcheck/cli/executor.py` | Cancel pending futures on interrupt; fix retry result cache |
| `netcheck/cli/batch.py` | Interrupt handling and `EXIT_BAD_ARGS` on empty targets |
| `netcheck/cli/watch.py` | ANSI screen clear; thread-safe rolling alert log list |
| `netcheck/modules/port_scanner.py` | Cancel pending port scan futures on `KeyboardInterrupt` |
| `netcheck/modules/interfaces.py` | Cancel pending public IP futures on early success and interrupt |
| `netcheck/utils/timeout.py` | Cancel future on `KeyboardInterrupt` in `run_with_timeout` |
| `netcheck/utils/formatters/json_fmt.py` | Added `udp` and `mtr` JSON formatting dispatch |
| `netcheck/utils/formatters/csv_fmt.py` | Added `udp` and `mtr` CSV formatting dispatch |
| `netcheck/utils/formatters/xml_fmt.py` | Added `udp` and `mtr` XML formatting dispatch |
| `netcheck/utils/cache.py` | `set()` — compute expiry inside lock; skip self-key in cleanup |
| `tests/unit/test_cache.py` | Deterministic TTL tests; 2 new edge-case tests |
| `tests/unit/test_mtr.py` | Rewritten for Python 3.8 compat — nested `with` |
| `tests/unit/test_udp.py` | Rewritten for Python 3.8 compat — nested `with` |
| `tests/cli/test_cli_main.py` | Unit test for `KeyboardInterrupt` exit code 130 |
| `tests/formatters/test_json_fmt.py` | Unit tests for UDP and MTR JSON formatting |
| `.github/workflows/ci.yml` | Replaced `flake8` lint step with `ruff check netcheck` |
| `.github/workflows/release.yml` | Fixed PowerShell syntax error + old repo URL in Winget step |
| `CHANGELOG.md` | Comprehensive v2.5.0 entry |
| `README.md` | Exit codes documentation table; updated badge and pkg version |
| `packaging/vscode/src/installer.ts` | Bumped `REQUIRED_VERSION` to `2.5.0` |
| `docs/releases/RELEASE_NOTES_V2.5.0.md` | Release documentation |

---

## Upgrade Guide

### Pip / pipx
```bash
pip install --upgrade netcheckx
# or
pipx upgrade netcheckx
```

### Snap (Linux)
```bash
sudo snap refresh netcheck
```

### Chocolatey (Windows)
```powershell
choco upgrade netcheck
```

### Debian package
```bash
sudo dpkg -i netcheck_2.5.0_amd64.deb
```

---

## Release Artefacts

| Artefact | Platform |
|----------|----------|
| `netcheckx-2.5.0-py3-none-any.whl` | PyPI / All platforms |
| `netcheckx-2.5.0.tar.gz` | Source distribution (PyPI) |
| `netcheck_2.5.0_amd64.deb` | Debian / Ubuntu |
| `netcheck_2.5.0_amd64.snap` | All Linux (Snap Store) |
| `netcheck-2.5.0-setup.exe` | Windows NSIS Installer |
| `netcheck-2.5.0.nupkg` | Windows Chocolatey |

---

## Full Changelog

See [CHANGELOG.md](../../CHANGELOG.md) for the complete history.
