# macOS Packaging

## Install Options

### Option 1 — Homebrew (Recommended)
```bash
brew tap farman20ali/netcheck
brew install netcheck
```

### Option 2 — pip
```bash
pip install netcheckx
netcheck --version
```

### Option 3 — macOS .pkg Installer
Download `netcheck-2.3.0.pkg` from GitHub Releases.
Double-click to install. NetCheck is placed in `/usr/local/bin/netcheck`.

## For Maintainers

Build the .pkg:
```bash
# Install dependencies into a staging dir
pip install netcheckx --target packaging/macos/stage/lib/python3.12/site-packages

# Create the pkg
pkgbuild \
  --root packaging/macos/stage \
  --identifier com.farman20ali.netcheck \
  --version 2.3.0 \
  --install-location /usr/local \
  netcheck-2.3.0.pkg

# Optionally sign (requires Apple Developer cert):
productsign --sign "Developer ID Installer: YOUR NAME" \
  netcheck-2.3.0.pkg netcheck-2.3.0-signed.pkg
```

Alternatively, use `py2app` to create a standalone .app bundle or `briefcase` (BeeWare) for a proper macOS app package.
