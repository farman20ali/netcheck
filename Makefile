.PHONY: help install uninstall test clean vscode-deps vscode-build vscode-dev vscode-publish vscode-clean

# Default target
help:
	@echo "Network Connectivity Checker (netcheck) - Make Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  make install     - Install netcheck system-wide (requires sudo)"
	@echo "  make uninstall   - Uninstall netcheck (requires sudo)"
	@echo "  make test        - Run unit tests using pytest"
	@echo "  make clean       - Clean temporary results and build artifacts"
	@echo ""
	@echo "Quick usage:"
	@echo "  sudo make install"

install:
	@./packaging/linux/install.sh

uninstall:
	@./packaging/linux/uninstall.sh

test:
	@if command -v pytest > /dev/null; then \
		PYTHONPATH=. pytest tests/ -v; \
	else \
		PYTHONPATH=. python3 -m pytest tests/ -v; \
	fi

clean:
	@echo "Cleaning temporary files and build caches..."
	@rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .benchmarks/
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@rm -f result-* fail-* combined-*
	@echo "Done!"

# ── VSCode Extension ─────────────────────────────────────────────────────────

## Install Node.js dependencies for the VSCode extension
vscode-deps:
	cd packaging/vscode && npm install

## Compile TypeScript and build .vsix package
vscode-build: vscode-deps
	cd packaging/vscode && npm run compile
	cd packaging/vscode && npx vsce package --no-dependencies

## Launch the Extension Development Host for interactive debugging
vscode-dev: vscode-deps
	cd packaging/vscode && npm run compile
	code --extensionDevelopmentPath=$(CURDIR)/packaging/vscode

## Publish extension to VS Code Marketplace (requires VSCODE_PAT env var)
vscode-publish: vscode-build
	@if [ -z "$(VSCODE_PAT)" ]; then \
		echo "Error: VSCODE_PAT is not set. Export it before running make vscode-publish."; \
		exit 1; \
	fi
	cd packaging/vscode && npx vsce publish --pat $(VSCODE_PAT)

## Remove compiled extension output
vscode-clean:
	@rm -rf packaging/vscode/out packaging/vscode/*.vsix packaging/vscode/node_modules

