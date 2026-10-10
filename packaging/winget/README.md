# winget Packaging (Windows)

## Install (users)
```powershell
winget install farman20ali.netcheck
```

## Update
```powershell
winget upgrade farman20ali.netcheck
```

## Uninstall
```powershell
winget uninstall farman20ali.netcheck
```

## For Maintainers

winget packages live in the winget-pkgs repo:
https://github.com/microsoft/winget-pkgs/tree/master/manifests/f/farman20ali/netcheck

To submit a new version:
1. Fork https://github.com/microsoft/winget-pkgs
2. Copy manifests/ to manifests/f/farman20ali/netcheck/2.x.x/
3. Update PackageVersion, InstallerUrl, InstallerSha256, ProductCode
4. Validate: `winget validate --manifest manifests/`
5. Submit PR to winget-pkgs

CI Auto-submit (add to release.yml):
Use the wingetcreate tool:
```powershell
wingetcreate update farman20ali.netcheck \
  --version $VERSION \
  --urls "https://github.com/.../netcheck-$VERSION-setup.exe" \
  --submit \
  --token $WINGET_GITHUB_TOKEN
```
