# AUR Packaging (Arch Linux)

## Install (users)
```bash
# Using yay
yay -S netcheck

# Using paru
paru -S netcheck

# Manual
git clone https://aur.archlinux.org/netcheck.git
cd netcheck
makepkg -si
```

## Uninstall
```bash
yay -R netcheck
```

## For Maintainers

The AUR package lives at: https://aur.archlinux.org/packages/netcheck

To update after a new release:
1. Update `pkgver` in PKGBUILD
2. Update `sha256sums` (run: `updpkgsums`)
3. Update `.SRCINFO`: `makepkg --printsrcinfo > .SRCINFO`
4. Push to AUR:
   ```bash
   git clone ssh://aur@aur.archlinux.org/netcheck.git
   # copy PKGBUILD and .SRCINFO
   git add PKGBUILD .SRCINFO
   git commit -m "Update to v2.x.x"
   git push
   ```

Requirements: You need an AUR account at https://aur.archlinux.org/register
