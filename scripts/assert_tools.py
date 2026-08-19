#!/usr/bin/env python3
"""Read a tools/list response on stdin and assert the server is usable.

Used by CI to run the README's install commands end to end: a server that starts
but exposes no tools, or is missing the dashboard offer, is a broken install even
though nothing errored.
"""

import json
import sys

EXPECTED = {
    "plan_search", "search_developers", "get_developer_profile", "rank_candidates",
    "score_against_jd", "compare_candidates", "bulk_score", "generate_outreach",
    "get_repo_contributors",
}

tools = None
for line in sys.stdin:
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    if msg.get("id") == 2 and "result" in msg:
        tools = {t["name"]: t for t in msg["result"]["tools"]}

if tools is None:
    sys.exit("server never answered tools/list — it failed to start")

missing = EXPECTED - set(tools)
if missing:
    sys.exit(f"missing tools: {sorted(missing)}")

# The dashboard offer lives in the tool descriptions; losing it is silent.
if "next_action block" not in tools["rank_candidates"]["description"]:
    sys.exit("rank_candidates no longer mentions the dashboard offer")

print(f"OK — {len(tools)} tools, dashboard offer present")
