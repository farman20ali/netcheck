# Homebrew Packaging

## Install
```bash
brew tap farman20ali/netcheck
brew install netcheck
```

## Update
```bash
brew upgrade netcheck
```

## Uninstall
```bash
brew uninstall netcheck
brew untap farman20ali/netcheck
```

## For Maintainers
Formula is at: https://github.com/farman20ali/homebrew-netcheck/blob/main/netcheck.rb

To update manually:
1. Update `url` to new PyPI tarball URL
2. Update `sha256` (run: `curl -sL <url> | sha256sum`)
3. Update version string
4. Test: `brew install --build-from-source ./netcheck.rb`
5. Push to homebrew-netcheck repo
