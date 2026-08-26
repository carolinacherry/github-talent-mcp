#!/usr/bin/env python3
"""Check the README's factual claims against the code.

Every check here exists because the claim was wrong at some point and cost a user
a debugging session. Run locally with: uv run python scripts/check_docs.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text()
PYPROJECT = (ROOT / "pyproject.toml").read_text()

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        failures.append(f"{name}{': ' + detail if detail else ''}")


def config_blocks() -> list[str]:
    """JSON config snippets the README tells users to paste."""
    return [b for b in re.findall(r"```(?:json|bash)\n(.*?)```", README, re.DOTALL) if "GITHUB_TOKEN" in b]


print("README accuracy checks\n")

# A token reference like ${GITHUB_TOKEN} expands to empty in a GUI app, which starts
# the server unauthenticated at 60 req/hr and fails searches with no error anywhere.
bad = [b for b in config_blocks() if "${GITHUB_TOKEN}" in b and "$TOKEN" not in b]
check("no config tells users to use ${GITHUB_TOKEN}", not bad, f"{len(bad)} block(s)")

# The Python badge is the first thing a user reads; if it overstates the requirement
# they never install at all.
declared = re.search(r'requires-python\s*=\s*"([^"]+)"', PYPROJECT).group(1)
badge = re.search(r"Python-([\d.]+)\+-blue", README)
check(
    "python badge matches requires-python",
    bool(badge) and declared.replace(">=", "") == badge.group(1),
    f"pyproject says {declared}, badge says {badge.group(1) if badge else 'none'}",
)

# A tool count that drifts makes users think their install is broken.
tools = sorted(re.findall(r"^async def ([a-z_]+)\(", (ROOT / "src/github_talent_mcp/server.py").read_text(), re.MULTILINE))
claimed = re.findall(r"you should see (\d+) tools", README)
check(
    f"README's tool count matches the server ({len(tools)})",
    all(int(c) == len(tools) for c in claimed) and claimed,
    f"server has {len(tools)}, README claims {set(claimed)}",
)

documented = set(re.findall(r"^\| `([a-z_]+)` \|", README, re.MULTILINE))
check("every tool is documented", set(tools) <= documented, f"missing: {set(tools) - documented}")
check("no documented tool is missing from the server", documented <= set(tools) | {"read:user", "public_repo"},
      f"phantom: {documented - set(tools)}")

# Manifests advertise a version users install from PyPI; a mismatch means someone
# installs a build that doesn't have what the manifest promises.
version = re.search(r'^version = "([^"]+)"', PYPROJECT, re.MULTILINE).group(1)
for manifest in [
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/plugin.json",
]:
    data = json.loads((ROOT / manifest).read_text())
    declared_v = data.get("version") or data["plugins"][0]["version"]
    check(f"{manifest} version matches pyproject", declared_v == version, f"{declared_v} vs {version}")

# The failure modes that actually break real runs must be documented.
check("unauthenticated rate limit is documented", "60 without one" in README)
check("search endpoint limit is documented", "30 requests/minute" in README)
check("the 3-line failure signature is documented", "Three lines means the call failed" in README)
check("the dashboard offer is documented", "Interactive dashboard" in README)
check("the dashboard kill switch is documented", "GITHUB_TALENT_DASHBOARD_PROMPT=0" in README)
check("Cloud Agent uvx ENOENT is documented", "spawn uvx ENOENT" in README)
check("Cloud Agent MCP + menu is documented", "**+** button" in README and "MCP Servers" in README)
check("Cloud Agents reject /home/box launcher is documented", "/home/box/bin/github-talent-mcp.sh" in README)
check("Cloud Agent Python bypass is documented", "proof of MCP" in README)
check("plugin ${GITHUB_TOKEN} vs PAT is documented", "plugin variable" in README)

print()
if failures:
    print(f"{len(failures)} inaccurate claim(s):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("README matches the code.")
