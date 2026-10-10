# Debian Packaging with `build_packages.py` (v2.3.0)

## Overview

A **.deb** package is the standard software package format for Debian-based Linux distributions (Ubuntu, Debian, Linux Mint, etc.). Instead of creating and maintaining debian structure files manually, `netcheck` automates the build process using the `build_packages.py` orchestrator.

---

## The Build Process

When you run `python build_packages.py --deb`, the builder executes the following steps:

1. **Verify Prerequisites**: Checks that `dpkg-buildpackage` and `fakeroot` are installed on the system.
2. **Create Temporary Workspace**: Spawns a unique temporary directory (e.g. `/tmp/netcheck-deb-XXXXXX`) and copies the codebase, excluding development artifacts (like `.git`, `.venv`, and test caches).
3. **Write Debian Skeleton**: Dynamically writes a standard Debian package layout under a new `debian/` folder.
4. **Compile Package**: Runs `dpkg-buildpackage -us -uc -rfakeroot` inside the temporary workspace.
5. **Collect Artifact**: Extracts the generated `.deb` package and copies it into the project's root `dist/deb/` directory, cleaning up all intermediate files.

---

## Dynamically Generated Debian Layout

The dynamically generated skeleton is written to conform strictly to Debian packaging standards:

### 1. `debian/control`
Declares the package metadata, architecture, dependencies, and descriptions:
```ini
Source: netcheck
Section: utils
Priority: optional
Maintainer: netcheck builder <netcheck@example.com>
Build-Depends: debhelper-compat (= 12)
Standards-Version: 4.6.2
Homepage: https://github.com/farman20ali/netcheck
Rules-Requires-Root: no

Package: netcheck
Architecture: all
Depends: ${misc:Depends}, python3, python3-cryptography, iproute2 | net-tools, iputils-ping
Description: Network connectivity checker (DNS, ping, HTTP, TCP, SSL)
 A cross-platform Python 3 engine for network diagnostics.
 Supports JSON/CSV/XML output, MCP server, and batch target testing.
```

### 2. `debian/rules`
The execution script that automates compilation and installation steps during build:
```makefile
#!/usr/bin/make -f

%:
	dh $@

override_dh_auto_install:
	install -d debian/netcheck/usr/bin
	install -d debian/netcheck/usr/lib/python3/dist-packages
	cp -r netcheck debian/netcheck/usr/lib/python3/dist-packages/
	find debian/netcheck/usr/lib/python3/dist-packages/netcheck -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	printf '#!/usr/bin/env python3\nimport sys\nfrom netcheck.cli import main\nsys.exit(main())\n' > debian/netcheck/usr/bin/netcheck
	chmod 755 debian/netcheck/usr/bin/netcheck

override_dh_auto_test:
	true
```

### 3. `debian/copyright`
Provides standard licensing information (GPL-3) required by lint tools like Lintian.

### 4. `debian/changelog`
Declares the version history. Formatted using standard RFC 2822 timestamps:
```text
netcheck (2.3.0-1) stable; urgency=medium

  * Release 2.3.0 — cross-platform Python 3 engine.

 -- netcheck builder <netcheck@example.com>  Thu, 30 Jul 2026 21:00:00 +0000
```

### 5. `debian/source/format`
Contains `3.0 (native)` to specify a native source package.

---

## How to Build

### Prerequisites
Install compilation requirements on your Debian/Ubuntu machine:
```bash
sudo apt install build-essential devscripts debhelper fakeroot dh-python python3-all
```

### Run Builder
```bash
python build_packages.py --deb
```
**Output**: The compiled package will be available at `dist/deb/netcheck_2.3.0-1_all.deb`.

---

## Local Verification & Installation

Install the compiled `.deb` package locally to test its behaviour:
```bash
# Install package
sudo dpkg -i dist/deb/netcheck_2.3.0-1_all.deb

# Verify installation path
which netcheck
# -> /usr/bin/netcheck

# Verify runtime execution
netcheck --version
netcheck tcp google.com 443 --json
```

To remove the package:
```bash
sudo apt remove netcheck
```

---

## Publishing Options

### 1. GitHub Releases
The easiest way is to attach the generated `.deb` package to a GitHub release.
```bash
python publish_packages.py --github-release v2.3.0
```
Users can then download and install it manually:
```bash
wget https://github.com/farman20ali/netcheck/releases/download/v2.3.0/netcheck_2.3.0-1_all.deb
sudo dpkg -i netcheck_2.3.0-1_all.deb
sudo apt-get install -f  # resolves any missing dependencies
```

### 2. Custom APT Repository
You can host the `.deb` file inside a static web server:
1. Copy the package to your pool: `cp dist/deb/*.deb apt-repo/pool/main/`
2. Re-index pool metadata: `dpkg-scanpackages pool/main /dev/null | gzip -9c > dists/stable/main/binary-amd64/Packages.gz`
3. Generate signed Release files.
4. Users add your repository to their `/etc/apt/sources.list.d/`.
