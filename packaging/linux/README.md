# Linux Packaging

## Install Options

### Option 1 — pip (All distros)
```bash
pip install netcheckx
netcheck --version
```

### Option 2 — Snap (All Linux)
```bash
sudo snap install netcheck
sudo snap connect netcheck:network-observe  # required for ping and --my-ip
```

### Option 3 — .deb (Debian / Ubuntu / Mint)
```bash
wget https://github.com/farman20ali/netcheck/releases/download/v2.3.0/netcheck_2.3.0_amd64.deb
sudo dpkg -i netcheck_2.3.0_amd64.deb
```

### Option 4 — RPM (Fedora / RHEL / CentOS / Amazon Linux)
*RPM packaging is on the roadmap for v2.5.0.*
Currently, use pip:
```bash
pip install netcheckx
```

### Option 5 — AUR (Arch / Manjaro)
```bash
yay -S netcheck
```

### Option 6 — Binary Tarball (Any Linux, no pip needed)
```bash
wget https://github.com/farman20ali/netcheck/releases/download/v2.3.0/netcheck-2.3.0-linux-x86_64.tar.gz
tar xzf netcheck-2.3.0-linux-x86_64.tar.gz
sudo mv netcheck /usr/local/bin/
netcheck --version
```

## Uninstall

| Method | Command |
|---|---|
| pip | `pip uninstall netcheckx` |
| snap | `sudo snap remove netcheck` |
| deb | `sudo apt remove netcheck` |
| tarball | `sudo rm /usr/local/bin/netcheck` |
| AUR | `yay -R netcheck` |

## For Maintainers — Building the Binary Tarball

Uses PyInstaller to create a single-file binary with no Python dependency:

```bash
pip install pyinstaller
pyinstaller --onefile --name netcheck netcheck/__main__.py
# Output: dist/netcheck
tar czf netcheck-2.3.0-linux-x86_64.tar.gz -C dist netcheck
```
