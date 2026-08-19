from __future__ import annotations

import json

from github_talent_mcp.github_client import GitHubClient
from github_talent_mcp.tools._offer import _attach_offer
from github_talent_mcp.scoring import score_jd_dimensions, generate_strengths_gaps
from github_talent_mcp.tools.profile import enrich_profiles


async def compare_candidates(
    client: GitHubClient,
    *,
    usernames: list[str],
    job_description: str | None = None,
) -> str:
    """Compare 2-5 GitHub candidates side-by-side with optional JD scoring."""
    if len(usernames) < 2:
        return json.dumps({"error": "Need at least 2 usernames to compare"})
    if len(usernames) > 5:
        return json.dumps({"error": "Max 5 candidates per comparison"})

    candidates = []

    profiles = await enrich_profiles(client, usernames)
    for username in usernames:
        profile = profiles[username]

        if "error" in profile:
            candidates.append({
                "username": username,
                "error": profile["error"],
            })
            continue

        entry: dict = {
            "username": username,
            "name": profile.get("name") or username,
            "profile_url": profile.get("html_url", f"https://github.com/{username}"),
            "top_languages": profile.get("top_languages", [])[:5],
            "followers": profile.get("followers", 0),
            "total_stars": profile.get("total_stars_received", 0),
            "activity_score": profile.get("activity_score", 0),
            "commits_90d": profile.get("commits_last_90_days", 0),
            "prs_90d": profile.get("prs_opened_last_90_days", 0),
            "notable_repos": [
                r.get("name") for r in profile.get("notable_repos", [])[:3]
                if isinstance(r, dict)
            ],
            "oss_contributions": profile.get("major_oss_contributions", [])[:3],
        }

        strengths, gaps = generate_strengths_gaps(profile)
        entry["strengths"] = strengths[:3]
        entry["gaps"] = gaps[:3]

        if job_description:
            jd_scores = score_jd_dimensions(profile, job_description)
            entry["jd_dimensions"] = jd_scores["dimensions"]
            entry["jd_overall_fit"] = jd_scores["overall_fit"]
            entry["jd_gaps"] = jd_scores["gaps"]

        candidates.append(entry)

    # Determine winners per dimension
    valid = [c for c in candidates if "error" not in c]
    winners: dict = {}

    if job_description and len(valid) >= 2:
        for dim in ["tech_stack_match", "experience_level", "oss_signal", "leadership_signals"]:
            best = max(valid, key=lambda c: c.get("jd_dimensions", {}).get(dim, 0))
            winners[dim] = best["username"]
        best_overall = max(valid, key=lambda c: c.get("jd_overall_fit", 0))
        winners["overall_fit"] = best_overall["username"]
    elif len(valid) >= 2:
        best_activity = max(valid, key=lambda c: c.get("activity_score", 0))
        winners["activity_score"] = best_activity["username"]
        best_stars = max(valid, key=lambda c: c.get("total_stars", 0))
        winners["total_stars"] = best_stars["username"]

    # Build recommendation
    recommendation = ""
    if job_description and valid:
        ranked = sorted(valid, key=lambda c: c.get("jd_overall_fit", 0), reverse=True)
        top = ranked[0]
        if len(ranked) >= 2:
            runner = ranked[1]
            diff = top.get("jd_overall_fit", 0) - runner.get("jd_overall_fit", 0)
            if diff >= 15:
                recommendation = f"{top['username']} is the clear frontrunner (overall {top['jd_overall_fit']} vs {runner['jd_overall_fit']})."
            elif diff >= 5:
                recommendation = f"{top['username']} edges out {runner['username']} ({top['jd_overall_fit']} vs {runner['jd_overall_fit']}), but both are worth interviewing."
            else:
                recommendation = f"{top['username']} and {runner['username']} are very close ({top['jd_overall_fit']} vs {runner['jd_overall_fit']}). Interview both."

    payload = {
        "candidates": candidates,
        "winners": winners,
        "recommendation": recommendation,
    }
    _attach_offer(payload, "compare", candidates, profiles)
    return json.dumps(payload, indent=2)
