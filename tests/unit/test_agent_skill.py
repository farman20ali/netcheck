"""
Unit tests for the NetCheck Agent Skill (skills/netcheck-diagnostics).

STDLIB-ONLY: No PyYAML or external parsers.

Design: pure helper functions take text strings; file-based tests call them.
This decouples logic from the filesystem and allows testing helpers directly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import netcheck
from netcheck.cli.subcommands import SUBCOMMANDS
from netcheck.mcp.tools import TOOLS_LIST

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "netcheck-diagnostics"
SKILL_MD = SKILL_DIR / "SKILL.md"
CLI_REF_MD = SKILL_DIR / "references" / "cli-reference.md"
MCP_REF_MD = SKILL_DIR / "references" / "mcp-reference.md"
SKILLS_README = REPO_ROOT / "skills" / "README.md"

# Inline code span containing a complete netcheck command
_INLINE_CMD_RE = re.compile(r"`(?:python(?:3)? -m )?netcheck [^`]+`")


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> dict:
    """Stdlib-only YAML frontmatter parser for simple key-value/nested metadata."""
    if not content.startswith("---"):
        raise ValueError("Missing leading '---' frontmatter boundary")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Unterminated frontmatter block")
    yaml_text = parts[1]
    data: dict = {}
    current_map: dict | None = None
    for line in yaml_text.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("  ") and current_map is not None:
            subline = line.strip()
            if ":" in subline:
                k, v = subline.split(":", 1)
                current_map[k.strip()] = v.strip().strip('"').strip("'")
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if v == "":
                current_map = {}
                data[k] = current_map
            else:
                current_map = None
                data[k] = v
    return data


def extract_fenced_code_blocks(text: str) -> list:
    """Return list of (start_line, lang_hint, content) for each fenced block."""
    blocks = []
    in_block = False
    lang = ""
    start = 0
    curr: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_block:
                blocks.append((start, lang, "\n".join(curr)))
                curr = []
                in_block = False
                lang = ""
            else:
                in_block = True
                start = i
                lang = stripped[3:].strip()
        elif in_block:
            curr.append(line)
    return blocks


def find_forbidden_flags(text: str) -> list:
    """
    Return (line_no, line, flag) triples where --watch, --alert, or -w (standalone)
    appear inside fenced code blocks.

    Additionally, inline backtick code spans that contain a complete netcheck command
    (matching _INLINE_CMD_RE) and also contain --watch, --alert, or standalone -w are
    flagged regardless of fence context.

    Bare prose mentions of the flag words (outside inline command spans) are NOT flagged,
    so the Forbidden Options section can describe them.
    """
    violations = []

    # --- Fenced block scan ---
    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            if "--watch" in line:
                violations.append((i, line, "--watch"))
            if "--alert" in line:
                violations.append((i, line, "--alert"))
            if re.search(r"(?:^|\s)-w(?:\s|$)", line):
                violations.append((i, line, "-w"))

    # --- Inline span scan: only flag spans that look like a complete command ---
    for i, line in enumerate(text.splitlines(), 1):
        for span_match in _INLINE_CMD_RE.finditer(line):
            span = span_match.group(0)
            if "--watch" in span:
                violations.append((i, line, "--watch (inline cmd span)"))
            if "--alert" in span:
                violations.append((i, line, "--alert (inline cmd span)"))
            if re.search(r"(?:^|\s)-w(?:\s|$)", span):
                violations.append((i, line, "-w (inline cmd span)"))

    return violations


def find_unknown_subcommands(text: str, known: set) -> list:
    """
    Scan fenced code blocks and inline backtick spans for netcheck <sub> patterns.
    Return (subcommand, context) for any sub not in known.
    Skips --version, --help, -h, -v; does NOT skip <subcommand> (dead code removed).
    Fenced-block lines must start with optional whitespace then the netcheck invocation.
    """
    skip = {"--version", "--help", "-h", "-v"}
    violations = []

    for _start, _lang, block_text in extract_fenced_code_blocks(text):
        for line in block_text.splitlines():
            # Anchor: line must start (optionally with spaces) or follow 'Run:' with the invocation
            m = re.search(r"(?:^\s*|(?:^|\s)Run:\s*)(?:python(?:3)? -m )?netcheck ([a-z0-9_-]+)", line)
            if m:
                sub = m.group(1)
                if sub not in skip and sub not in known:
                    violations.append((sub, f"fenced block: {repr(line.strip())}"))

    for m in re.finditer(r"`(?:python(?:3)? -m )?netcheck ([a-z0-9_-]+)", text):
        sub = m.group(1)
        if sub not in skip and sub not in known:
            violations.append((sub, f"inline span: {repr(m.group(0))}"))

    return violations


def find_local_paths(text: str) -> list:
    """Return (line_no, line, pattern) for machine-specific local path strings."""
    PATTERNS = [
        re.compile(r"file:///", re.IGNORECASE),
        re.compile(r"d:/", re.IGNORECASE),
        re.compile(r"d:\\", re.IGNORECASE),
        re.compile(r"workspace", re.IGNORECASE),
        re.compile(r"desktop-", re.IGNORECASE),
        re.compile(r"wi-fi", re.IGNORECASE),
        re.compile(r"svchost", re.IGNORECASE),
        re.compile(r"192\.168\."),
        re.compile(r"C:\\Users", re.IGNORECASE),
        re.compile(r"\b10\.\d{1,3}\."),
        re.compile(r"\b172\.(?:1[6-9]|2\d|3[01])\."),
        re.compile(r"vEthernet", re.IGNORECASE),
        re.compile(r"\bWSL\b", re.IGNORECASE),
        re.compile(r"Hyper-V", re.IGNORECASE),
    ]
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for pat in PATTERNS:
            if pat.search(line):
                hits.append((i, line, pat.pattern))
    return hits


def parse_json_blocks(text: str) -> list:
    """
    Return (block_index, error_or_None) for every ```json block in text.
    Blocks whose first non-whitespace line is a comment (# template) are skipped.
    Placeholders <...> inside quoted strings are left as-is (valid JSON string chars).
    Bare numeric placeholders like <port> outside quotes are NOT rewritten; they must fail.
    """
    results = []
    QUOTED_PH = re.compile(r'"[^"]*<[^>]+>[^"]*"')
    for idx, (_start, lang, block) in enumerate(extract_fenced_code_blocks(text), 1):
        if lang.strip() != "json":
            continue
        first = block.strip().splitlines()[0] if block.strip() else ""
        if first.startswith("#"):
            results.append((idx, None))  # template block, skip
            continue
        # Normalise placeholders inside quoted strings only
        b = QUOTED_PH.sub('"PLACEHOLDER"', block)
        try:
            json.loads(b)
            results.append((idx, None))
        except json.JSONDecodeError as e:
            results.append((idx, str(e)))
    return results


def check_section7_headings(text: str) -> dict:
    """
    Check that text contains the four required headings in Section 7:
    'Observed Facts', 'Unknowns', 'Hypotheses', 'Recommended Next Step'.
    Returns dict mapping heading -> bool (present).
    """
    sec7_match = re.search(r"## 7\..*?(?=##|\Z)", text, re.DOTALL)
    sec7_text = sec7_match.group(0) if sec7_match else text
    required = ["Observed Facts", "Unknowns", "Hypotheses", "Recommended Next Step"]
    return {h: bool(re.search(rf"\*\*{re.escape(h)}:?\*\*", sec7_text)) for h in required}


BANNED_PHRASES = (
    "RST packet",
    "likely cause",
    "Keep the Windows-only scope",
    "do not define or assume",
)


def find_banned_phrases(text: str, banned: tuple = BANNED_PHRASES) -> list:
    """Return list of (line_no, line, phrase) for occurrences of banned phrases (case-insensitive)."""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for phrase in banned:
            if re.search(re.escape(phrase), line, re.IGNORECASE):
                hits.append((i, line, phrase))
    return hits


def find_likely_cause(text: str) -> list:
    """Return list of (line_no, line) for occurrences of 'likely cause' (case-insensitive)."""
    return [(line_no, line) for line_no, line, _ in find_banned_phrases(text, banned=("likely cause",))]


def heading_to_anchor(heading: str) -> str:
    """Generate GitHub-style anchor slug from heading text (lowercase, spaces to hyphens, punctuation removed)."""
    h = re.sub(r"[#*_`]", "", heading).strip().lower()
    h = re.sub(r"[^\w\s-]", "", h)
    h = re.sub(r"\s+", "-", h)
    return h


def extract_markdown_anchors(text: str) -> set[str]:
    """Extract all GitHub-style anchors from markdown headings in text."""
    anchors = set()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            heading_text = line.lstrip("#").strip()
            if heading_text:
                anchors.add(heading_to_anchor(heading_text))
    return anchors


def verify_relative_link(source_path: Path, link: str) -> tuple[bool, str]:
    """
    Verify relative link and optional #anchor against target file.
    Returns (is_valid, error_message).
    """
    if link.startswith("http://") or link.startswith("https://") or link.startswith("mailto:"):
        return True, ""

    parts = link.split("#", 1)
    file_part = parts[0]
    anchor_part = parts[1] if len(parts) > 1 else None

    if file_part:
        target_path = (source_path.parent / file_part).resolve()
    else:
        target_path = source_path

    if not target_path.exists():
        return False, f"File does not exist: {target_path}"

    if anchor_part:
        content = target_path.read_text(encoding="utf-8")
        anchors = extract_markdown_anchors(content)
        if anchor_part not in anchors:
            return False, f"Anchor #{anchor_part} not found in {target_path.name}. Available anchors: {sorted(anchors)}"

    return True, ""


# ---------------------------------------------------------------------------
# Tests on literal strings (pure, no filesystem)
# ---------------------------------------------------------------------------

class TestHelpersOnLiteralStrings:
    def test_forbidden_flags_clean_prose(self):
        """Prose mention of --watch is allowed."""
        text = "Do not use --watch outside explicit user request."
        assert find_forbidden_flags(text) == []

    def test_forbidden_flags_watch_in_fence(self):
        """--watch inside a fenced block is a violation."""
        text = "Example:\n```bash\nnetcheck tcp host 80 --watch\n```"
        v = find_forbidden_flags(text)
        assert any("--watch" in v2[2] for v2 in v), v

    def test_forbidden_flags_alert_in_fence(self):
        """--alert inside a fenced block is a violation."""
        text = "```bash\nnetcheck http https://example.com --alert email\n```"
        v = find_forbidden_flags(text)
        assert any("--alert" in v2[2] for v2 in v), v

    def test_forbidden_flags_inline_cmd_watch_fails(self):
        """An inline code span that is a complete netcheck command with --watch is a violation."""
        text = "Run `netcheck tcp host 80 --watch` to monitor."
        v = find_forbidden_flags(text)
        assert any("--watch" in v2[2] for v2 in v), v

    def test_forbidden_flags_inline_bare_prose_ok(self):
        """Bare prose mention of --watch (not in a command span) is NOT a violation."""
        text = "The --watch flag loops indefinitely."
        assert find_forbidden_flags(text) == []

    def test_unknown_subcommands_known_clean(self):
        known = {"tcp", "dns", "ping"}
        text = "```bash\nnetcheck tcp 127.0.0.1 80 -f json\n```"
        assert find_unknown_subcommands(text, known) == []

    def test_unknown_subcommands_unknown_in_fence(self):
        known = {"tcp", "dns"}
        text = "```bash\nnetcheck frobnicate host 80\n```"
        v = find_unknown_subcommands(text, known)
        assert any(v2[0] == "frobnicate" for v2 in v), v

    def test_unknown_subcommands_python_m_prefix(self):
        known = {"dns"}
        text = "```bash\npython -m netcheck dns example.com -f json\n```"
        assert find_unknown_subcommands(text, known) == []

    def test_unknown_subcommands_python3_prefix(self):
        known = {"ping"}
        text = "```bash\npython3 -m netcheck ping 127.0.0.1\n```"
        assert find_unknown_subcommands(text, known) == []

    def test_unknown_subcommands_fenced_anchor(self):
        """An English word after 'netcheck' in prose inside a fence is NOT a false positive."""
        known = {"tcp"}
        # 'foo' appears after netcheck in a comment, not as an invocation
        text = "```bash\n# netcheck does a lot\nnetcheck tcp host 80\n```"
        v = find_unknown_subcommands(text, known)
        # 'a' and 'lot' and 'does' must not be flagged
        assert all(s not in ("a", "lot", "does") for s, _ in v), v

    def test_unknown_subcommands_run_prefix_bad_fails(self):
        """A bad subcommand preceded by 'Run:' inside a fence must be flagged."""
        known = {"tcp", "dns"}
        text = "```\n   |    => Run: netcheck frobnicate host 80\n```"
        v = find_unknown_subcommands(text, known)
        assert any(sub == "frobnicate" for sub, _ in v), v

    def test_local_paths_clean(self):
        text = "Use `netcheck/modules/ping.py` to understand the code."
        assert find_local_paths(text) == []

    def test_local_paths_detects_file_scheme(self):
        text = "See [file](file:///d:/workspace/dev/netcheck/foo.py)"
        hits = find_local_paths(text)
        assert len(hits) > 0

    def test_local_paths_flags_192_168_address(self):
        text = "Target IP is 192.168.1.1 for local testing."
        hits = find_local_paths(text)
        assert len(hits) > 0

    def test_local_paths_flags_d_drive_backslash(self):
        text = r"Check file at d:\project\foo.py"
        hits = find_local_paths(text)
        assert len(hits) > 0

    def test_local_paths_flags_c_users_path(self):
        text = r"Logs saved in C:\Users\HP\AppData\Local"
        hits = find_local_paths(text)
        assert len(hits) > 0

    def test_local_paths_flags_10_x_address(self):
        text = "Private IP is 10.0.0.1 for router."
        hits = find_local_paths(text)
        assert len(hits) > 0

    def test_local_paths_flags_172_16_31_x_address(self):
        text = "Subnet is 172.26.16.1 on internal bridge."
        hits = find_local_paths(text)
        assert len(hits) > 0

    def test_local_paths_flags_vethernet(self):
        text = "Interface named vEthernet (Default Switch) detected."
        hits = find_local_paths(text)
        assert len(hits) > 0

    def test_local_paths_flags_wsl(self):
        text = "Found adapter for WSL network."
        hits = find_local_paths(text)
        assert len(hits) > 0

    def test_local_paths_flags_hyperv(self):
        text = "Virtual switch configured with Hyper-V."
        hits = find_local_paths(text)
        assert len(hits) > 0

    def test_json_blocks_valid(self):
        text = '''Some text\n```json\n{"key": "value"}\n```\n'''
        results = parse_json_blocks(text)
        assert all(err is None for _, err in results), results

    def test_json_blocks_invalid(self):
        text = '''```json\n{bad json}\n```'''
        results = parse_json_blocks(text)
        assert any(err is not None for _, err in results), results

    def test_json_blocks_bare_placeholder_fails(self):
        """A bare numeric placeholder <port> outside quotes must fail JSON parsing."""
        text = '''```json\n{"port": <port>}\n```'''
        results = parse_json_blocks(text)
        assert any(err is not None for _, err in results), results

    def test_section7_headings_literal_all_present(self):
        text = (
            "## 7. Example Report\n\n"
            "**Observed Facts:**\n- some fact\n\n"
            "**Unknowns:**\n- some unknown\n\n"
            "**Hypotheses:**\n- hypothesis 1\n\n"
            "**Recommended Next Step:**\n- next step\n"
        )
        res = check_section7_headings(text)
        assert all(res.values()), res

    def test_section7_headings_literal_missing(self):
        text = (
            "## 7. Example Report\n\n"
            "**Observed Facts:**\n- some fact\n\n"
            "**Hypotheses:**\n- hypothesis 1\n"
        )
        res = check_section7_headings(text)
        assert res["Unknowns"] is False
        assert res["Recommended Next Step"] is False

    def test_likely_cause_clean_literal(self):
        text = "Hypotheses are consistent with the evidence, listed unranked."
        assert find_likely_cause(text) == []

    def test_likely_cause_flagged_literal(self):
        text = "The likely cause of this issue is an upstream network partition."
        hits = find_likely_cause(text)
        assert len(hits) == 1
        assert hits[0][0] == 1

    def test_banned_phrase_rst_packet_fails(self):
        text = "The host actively rejected the connection with a RST packet."
        hits = find_banned_phrases(text)
        assert any(p == "RST packet" for _, _, p in hits), hits

    def test_banned_phrase_likely_cause_fails(self):
        text = "This is the most likely cause of connection reset."
        hits = find_banned_phrases(text)
        assert any(p == "likely cause" for _, _, p in hits), hits

    def test_banned_phrase_windows_only_scope_fails(self):
        text = "Keep the Windows-only scope and proceed."
        hits = find_banned_phrases(text)
        assert any(p == "Keep the Windows-only scope" for _, _, p in hits), hits

    def test_banned_phrase_do_not_define_or_assume_fails(self):
        text = "Please do not define or assume any numeric threshold."
        hits = find_banned_phrases(text)
        assert any(p == "do not define or assume" for _, _, p in hits), hits

    def test_banned_phrases_clean_literal(self):
        text = "All checks passed without any forbidden terminology."
        assert find_banned_phrases(text) == []

    def test_anchor_helper_matching_literal(self):
        heading = "6. Strict Safety Guardrails"
        slug = heading_to_anchor(heading)
        assert slug == "6-strict-safety-guardrails"
        text = "## 6. Strict Safety Guardrails\n\nSome safety notes."
        anchors = extract_markdown_anchors(text)
        assert "6-strict-safety-guardrails" in anchors

    def test_anchor_helper_mismatch_literal(self):
        text = "## 6. Strict Safety Guardrails\n\nSome safety notes."
        anchors = extract_markdown_anchors(text)
        # The old slug '6-safety--ethics' does not match the real heading
        assert "6-safety--ethics" not in anchors


# ---------------------------------------------------------------------------
# File-based tests
# ---------------------------------------------------------------------------

class TestAgentSkillFrontmatter:
    def test_skill_files_exist(self):
        assert SKILL_DIR.is_dir()
        assert SKILL_MD.is_file()
        assert CLI_REF_MD.is_file()
        assert MCP_REF_MD.is_file()

    def test_frontmatter_constraints(self):
        content = SKILL_MD.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)

        name = fm.get("name")
        assert name is not None
        assert name == SKILL_DIR.name
        assert 1 <= len(name) <= 64
        assert re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name)

        desc = fm.get("description")
        assert desc is not None
        assert 1 <= len(desc) <= 1024

        assert fm.get("license") == "GPL-3.0-only"

        comp = fm.get("compatibility", "")
        assert ">=3.8" in comp

        meta = fm.get("metadata", {})
        assert meta.get("version") == netcheck.__version__

        assert "allowed-tools" not in fm

    def test_skill_md_under_300_lines(self):
        lines = SKILL_MD.read_text(encoding="utf-8").splitlines()
        assert len(lines) < 300, f"SKILL.md has {len(lines)} lines (must be < 300)"

    def test_relative_links_resolve(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
            target = m.group(2)
            if target.startswith("http") or target.startswith("#"):
                continue
            resolved = SKILL_MD.parent / target
            assert resolved.exists(), f"Relative link broken: {target!r} -> {resolved}"

    def test_skills_readme_relative_links_and_anchors(self):
        text = SKILLS_README.read_text(encoding="utf-8")
        for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
            target = m.group(2)
            ok, msg = verify_relative_link(SKILLS_README, target)
            assert ok, f"In skills/README.md: {msg}"



class TestAgentSkillParity:
    def test_mcp_tools_parity(self):
        content = MCP_REF_MD.read_text(encoding="utf-8")
        code_names = {t["name"] for t in TOOLS_LIST}
        doc_names = set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", content, re.MULTILINE))
        assert doc_names == code_names, (
            f"In doc not code: {doc_names - code_names}; in code not doc: {code_names - doc_names}"
        )

    def test_udp_mtr_not_mcp_tools(self):
        content = MCP_REF_MD.read_text(encoding="utf-8")
        doc_names = set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", content, re.MULTILINE))
        for bad in ("udp", "mtr", "check_udp", "check_mtr"):
            assert bad not in doc_names

    def test_cli_subcommands_in_dispatcher(self):
        known = set(SUBCOMMANDS)
        for path in (SKILL_MD, CLI_REF_MD):
            text = path.read_text(encoding="utf-8")
            v = find_unknown_subcommands(text, known)
            assert v == [], f"Unknown subcommands in {path.name}: {v}"

    def test_no_watch_alert_in_references(self):
        for path in (CLI_REF_MD, MCP_REF_MD):
            text = path.read_text(encoding="utf-8")
            assert "--watch" not in text
            assert "--alert" not in text
            assert not re.search(r"(?:^|\s)-w(?:\s|$)", text)

    def test_no_watch_alert_in_skill_fenced_or_inline_cmd(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        v = find_forbidden_flags(text)
        assert v == [], f"Forbidden flags in SKILL.md: {v}"

    def test_no_local_machine_paths(self):
        for path in (SKILL_MD, CLI_REF_MD, MCP_REF_MD, SKILLS_README):
            text = path.read_text(encoding="utf-8")
            hits = find_local_paths(text)
            assert hits == [], f"Local paths in {path.name}: {hits}"

    def test_all_json_blocks_parse(self):
        for path in (CLI_REF_MD, MCP_REF_MD):
            text = path.read_text(encoding="utf-8")
            results = parse_json_blocks(text)
            failures = [(i, e) for i, e in results if e is not None]
            assert failures == [], f"JSON parse failures in {path.name}: {failures}"

    def test_skill_md_section7_required_headings(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        res = check_section7_headings(text)
        for heading, present in res.items():
            assert present, f"Missing required Section 7 heading: {heading}"

    def test_skill_md_no_likely_cause(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        hits = find_likely_cause(text)
        assert hits == [], f"Found 'likely cause' in SKILL.md: {hits}"

    def test_skill_md_no_banned_phrases(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        hits = find_banned_phrases(text)
        assert hits == [], f"Found banned phrases in SKILL.md: {hits}"


