# Windows Package Manager (winget) Packaging

This directory contains the official winget manifests and instructions for publishing **NetCheck** to the Microsoft Community Repository ([microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs)).

---

## Directory Structure

Manifests strictly follow the Windows Package Manager repository format:

```
packaging/winget/
├── README.md
└── manifests/
    └── a/
        └── AlienHub/
            └── NetCheck/
                └── 2.4.0/
                    ├── AlienHub.NetCheck.yaml               # Version manifest
                    ├── AlienHub.NetCheck.installer.yaml     # Installer metadata & SHA256
                    └── AlienHub.NetCheck.locale.en-US.yaml  # Package description, license & links
```

- **Package Identifier**: `AlienHub.NetCheck`
- **First Letter**: `a`
- **Installer Type**: `nullsoft` (NSIS setup executable)
- **Scope**: `machine`

---

## Validation

Before submitting any manifest, validate it locally using `winget`:

```powershell
winget validate --manifest packaging\winget\manifests\a\AlienHub\NetCheck\2.4.0
```

---

## How to Publish

### 1. First-Time Submission (Initial Publication)

Because `AlienHub.NetCheck` is not yet present in `microsoft/winget-pkgs`, `wingetcreate update` cannot be used for the very first release. You must submit the initial package manifest to create the package in the repository.

#### Option A: Automatic Submission with `wingetcreate` (Recommended)

Run the following command in PowerShell:

```powershell
wingetcreate submit packaging\winget\manifests\a\AlienHub\NetCheck\2.4.0 `
  --prtitle "New package: AlienHub.NetCheck version 2.4.0" `
  --token (gh auth token)
```

> **Note**: `wingetcreate` will automatically fork `microsoft/winget-pkgs`, create a feature branch, commit the manifests, and open the pull request for you. If you don't use `--token`, it will prompt for your GitHub authorization in the browser.

#### Option B: Manual PR via GitHub

1. Fork [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) to your GitHub account.
2. Clone your fork:
   ```bash
   git clone https://github.com/farman20ali/winget-pkgs.git
   cd winget-pkgs
   git checkout -b AlienHub.NetCheck-2.4.0
   ```
3. Copy the manifest folder:
   Copy `packaging/winget/manifests/a` into the root `manifests/` folder of the cloned `winget-pkgs` repository so it resides at:
   `manifests/a/AlienHub/NetCheck/2.4.0/`
4. Commit and push:
   ```bash
   git add manifests/a/AlienHub/NetCheck/2.4.0/
   git commit -m "New package: AlienHub.NetCheck version 2.4.0"
   git push origin AlienHub.NetCheck-2.4.0
   ```
5. Open a Pull Request against `microsoft:master`.
6. Microsoft's automated bots (`Azure Pipelines`) will validate the installer download, check hashes, scan for viruses via VirusTotal, and test silent installation in Windows Sandbox. Once approved, it is merged and published within a few hours.

---

### 2. Updating Future Releases (v2.5.0+)

Once the initial PR is merged into `microsoft/winget-pkgs`, you can publish every future release using:

#### Via GitHub Actions CI (Automatic)
The workflow in `.github/workflows/release.yml` includes a `publish-winget` job that automatically executes upon pushing a release tag (e.g., `v2.5.0`):

```powershell
wingetcreate update AlienHub.NetCheck `
  --version $VERSION `
  --urls "https://github.com/farman20ali/netcheck/releases/download/$TAG_NAME/netcheck-$VERSION-setup.exe" `
  --submit `
  --token $env:WINGET_GITHUB_TOKEN
```

#### Via CLI (Manual)
Once the release assets are published on GitHub Releases:

```powershell
wingetcreate update AlienHub.NetCheck `
  --version 2.5.0 `
  --urls "https://github.com/farman20ali/netcheck/releases/download/v2.5.0/netcheck-2.5.0-setup.exe" `
  --submit `
  --token (gh auth token)
```

---

## User Installation & Commands

Once merged in the official winget repository:

### Install
```powershell
winget install netcheck
# Or explicitly:
winget install AlienHub.NetCheck
```

### Upgrade
```powershell
winget upgrade netcheck
```

### Uninstall
```powershell
winget uninstall AlienHub.NetCheck
```
