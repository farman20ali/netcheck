# Windows Packaging

## Install Options

### Option 1 — winget (Recommended for Windows 10/11)
```powershell
winget install farman20ali.netcheck
```

### Option 2 — Chocolatey
```powershell
choco install netcheck
```

### Option 3 — NSIS Installer (.exe)
Download `netcheck-2.3.0-setup.exe` from GitHub Releases.
Run as Administrator. NetCheck is added to PATH automatically.

### Option 4 — pip
```powershell
pip install netcheckx
netcheck --version
```

### Option 5 — Scoop (no admin needed)
```powershell
# Add the bucket:
scoop bucket add farman20ali https://github.com/farman20ali/scoop-netcheck
scoop install netcheck
```

## Notes

- ICMP ping (`-p / --ping`) requires **Administrator** on Windows (Windows restricts raw socket access to admin).
- All other features (TCP, DNS, HTTP, SSL, traceroute, WHOIS, scan) work without admin.
- Tested on Windows 10 21H2+ and Windows 11.

## Uninstall

| Method | Command |
|---|---|
| winget | `winget uninstall farman20ali.netcheck` |
| Chocolatey | `choco uninstall netcheck` |
| .exe installer | Control Panel → Add/Remove Programs → NetCheck |
| pip | `pip uninstall netcheckx` |
| Scoop | `scoop uninstall netcheck` |

## For Maintainers — Building the .exe

Uses NSIS (Nullsoft Scriptable Install System):

```bash
makensis packaging/windows/installer.nsi
```
