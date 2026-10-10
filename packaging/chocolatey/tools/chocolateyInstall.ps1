$ErrorActionPreference = 'Stop';

$packageName = 'netcheck'
$toolsDir   = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"
$version    = '{version}'
$url64      = "https://github.com/farman20ali/netcheck/releases/download/v$version/netcheck-$version-setup.exe"
$checksum64 = '{checksum64}'

Write-Host "Downloading netcheck v$version from GitHub releases..."

# Download the Windows installer from GitHub releases
$installerPath = Join-Path $toolsDir "netcheck-$version-setup.exe"

Get-ChocolateyWebFile -PackageName $packageName `
                      -FileFullPath $installerPath `
                      -Url $url64 `
                      -Checksum $checksum64 `
                      -ChecksumType 'sha256'

Write-Host "Running netcheck installer..."

# Run the NSIS installer with silent mode
$installArgs = "/S"
Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait

# Clean up the installer
Remove-Item $installerPath -Force -ErrorAction SilentlyContinue

Write-Host "netcheck installed successfully!"
Write-Host "Verify installation with: netcheck --version"
