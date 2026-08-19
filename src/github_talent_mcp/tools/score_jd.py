from __future__ import annotations

import json

from github_talent_mcp.github_client import GitHubClient
from github_talent_mcp.tools._offer import _attach_offer
from github_talent_mcp.scoring import score_jd_dimensions, generate_strengths_gaps
from github_talent_mcp.tools.profile import enrich_profiles


async def score_against_jd(
    client: GitHubClient,
    *,
    job_description: str,
    usernames: list[str],
    top_n: int = 10,
) -> str:
    """Score candidates against a job description with per-dimension breakdown."""
    results = []

    profiles = await enrich_profiles(client, usernames)
    for username in usernames:
        profile = profiles[username]

        if "error" in profile:
            results.append({
                "rank": 0,
                "username": username,
                "overall_fit": 0,
                "dimensions": {},
                "strengths": [],
                "gaps": ["Profile unavailable"],
                "interview_questions": [],
                "profile_url": f"https://github.com/{username}",
            })
            continue

        jd_scores = score_jd_dimensions(profile, job_description)
        strengths, gaps = generate_strengths_gaps(profile)

        # Merge JD-specific gaps with general gaps
        all_gaps = jd_scores["gaps"] + [g for g in gaps if g not in jd_scores["gaps"]]

        results.append({
            "rank": 0,
            "username": username,
            "overall_fit": jd_scores["overall_fit"],
            "dimensions": jd_scores["dimensions"],
            "required_level": jd_scores["required_level"],
            "estimated_candidate_level": jd_scores["estimated_candidate_level"],
            "strengths": strengths,
            "gaps": all_gaps,
            "interview_questions": jd_scores["interview_questions"],
            "profile_url": profile.get("html_url", f"https://github.com/{username}"),
        })

    results.sort(key=lambda r: r["overall_fit"], reverse=True)
    for i, r in enumerate(results[:top_n], 1):
        r["rank"] = i

    payload = {
        "job_description_summary": job_description[:200],
        "total_evaluated": len(results),
        "candidates": results[:top_n],
    }
    payload = _attach_offer(payload, "score_jd", payload["candidates"], profiles)
    return json.dumps(payload, indent=2)
