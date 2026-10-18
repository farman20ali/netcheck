# NetCheck Diagnostics Skill

## Overview
The `netcheck-diagnostics` skill provides instructions and references for an AI agent diagnosing network connectivity issues with NetCheck.

What the skill is:
- A structured guide for AI coding agents to select appropriate NetCheck subcommands or MCP tools and interpret output.

What the skill is not:
- It does not install NetCheck.
- It does not grant execution permissions or elevate privileges.
- It does not configure or manage MCP client settings.

## Prerequisites
- Python >= 3.8
- NetCheck installed via pip or pipx:
  - `pip install netcheckx` or `pipx install netcheckx`
- Verify installation:
  - `netcheck --version`

## Installation
Copy the `netcheck-diagnostics/` folder into your agent's skills directory.

| Agent | Project Skills Path | User Skills Path | Source |
|---|---|---|---|
| Antigravity | `.agents/skills/` | `~/.gemini/config/skills/` | Antigravity's built-in customization docs (no public link found) |
| GitHub Copilot | `.github/skills/`<br>`.claude/skills/`<br>`.agents/skills/` | `~/.copilot/skills/`<br>`~/.claude/skills/`<br>`~/.agents/skills/` | [GitHub Copilot documentation](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` | [Claude Code skills documentation](https://code.claude.com/docs/en/skills) |

Claude Code's documentation lists `.claude/skills/` only; it does not list `.agents/skills/`.

## MCP Setup
- `netcheck mcp install` prints a sample configuration snippet (read-only; does not write client configs).
- Server command actually run: `python -m netcheck mcp` (verified). Read from code but not run: `netcheck mcp`, `netcheck --mcp`.
- MCP clients differ in configuration file format and location; refer to your client's documentation.
- The skill works with CLI only; MCP is optional.

## Verified On
- Captures and verified outputs were taken on Windows using loopback endpoints only (`127.0.0.1`, `::1`, `localhost`).
- Linux and macOS error strings and behaviors are expected based on platform sockets, but are unverified.
- Manual agent tests so far used a NetCheck 2.4.0 binary on PATH and one agent; they have not been repeated on 2.5.0.
- Uncaptured subcommands and tools (outputs not captured via live test runs):
  - `traceroute`
  - `scan` / `scan_ports`
  - `whois` / `whois_lookup`
  - `ssl` / `check_ssl_certificate`
  - `udp` (CLI-only)
  - `mtr` (CLI-only)

## Safety and Known Limitations
- Safety: review [SKILL.md §6](netcheck-diagnostics/SKILL.md#6-strict-safety-guardrails) before scanning or diagnosing external networks. Do not scan CIDR ranges or third-party targets without explicit authorization.
- Known limitations:
  - No range size cap: NetCheck does not enforce bounds on CIDR masks or port ranges. Large ranges must be confirmed with the user.
  - Windows short timeouts: a 1 s timeout was observed to report 'timed out' for a refused port on Windows; other values were not measured.
  - CLI-only subcommands: `udp` and `mtr` have no MCP tool equivalents.

## Testing
Run the skill unit tests:
```bash
pytest tests/unit/test_agent_skill.py
```

## License
GPL-3.0-only, same as the repository.

