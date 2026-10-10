# Release Notes — NetCheck v2.5.0

**Release Date:** 2026-10-10
**Type:** Maintenance — CI Reliability, Repository Rename, Bug Fixes & Test Hardening

---

## Overview

v2.5.0 is a maintenance and stability release. It completes the repository rename from
`network_access_check` to `netcheck` across every packaging pipeline, hardens the CI matrix
by switching the lint step from `flake8` (which was absent from `dev` dependencies) to `ruff`
(already present), fixes a Python 3.10+ syntax incompatibility that crashed the test runner on
Python 3.8/3.9, and resolves a timer-jitter flakiness in the cache TTL test suite.

No public API or CLI behaviour changes. All existing commands, flags, and config formats remain
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

## Breaking Changes

None.

---

## Files Changed

| File | Change |
|------|--------|
| `netcheck/__init__.py` | Version bumped to `2.5.0` |
| `pyproject.toml` | Version bumped to `2.5.0` |
| `netcheck/cli/subcommands.py` | Removed unused `global _metrics_registry` (`F824`) |
| `netcheck/cli/main.py` | Replaced invalid `# noqa: unreachable` with plain comment |
| `netcheck/post_install.py` | Sorted `__future__` import block (`ruff I001`) |
| `netcheck/utils/cache.py` | `set()` — compute expiry inside lock; skip self-key in cleanup |
| `tests/unit/test_cache.py` | Replaced `time.sleep` with `patch(time)` for deterministic TTL tests; 2 new tests |
| `tests/unit/test_mtr.py` | Rewritten for Python 3.8 compat — nested `with` instead of parenthesized form |
| `tests/unit/test_udp.py` | Rewritten for Python 3.8 compat — nested `with` instead of parenthesized form |
| `.github/workflows/ci.yml` | Replaced `flake8` lint step with `ruff check netcheck` |
| `.github/workflows/release.yml` | Fixed PowerShell syntax error + old repo URL in Winget step |
| `CHANGELOG.md` | v2.5.0 entry added |
| `README.md` | Version badge and `.deb` filename updated to `2.5.0` |
| `packaging/snap/snapcraft.yaml` | Version bumped to `2.5.0` |
| `docs/releases/RELEASE_NOTES_V2.5.0.md` | This file |

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
