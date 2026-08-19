from __future__ import annotations

import json

from github_talent_mcp.github_client import GitHubClient
from github_talent_mcp.tools._offer import _attach_offer
from github_talent_mcp.scoring import (
    compute_relevance_score,
    extract_keywords,
    generate_strengths_gaps,
)
from github_talent_mcp.tools.profile import enrich_profiles


async def rank_candidates(
    client: GitHubClient,
    *,
    usernames: list[str],
    job_description: str,
    top_n: int = 10,
) -> str:
    keywords = extract_keywords(job_description)
    candidates = []

    profiles = await enrich_profiles(client, usernames)
    for username in usernames:
        profile = profiles[username]

        if "error" in profile:
            candidates.append({
                "rank": 0,
                "username": username,
                "score": 0,
                "reasoning": f"Could not fetch profile: {profile['error']}",
                "strengths": [],
                "gaps": ["Profile unavailable"],
                "profile_url": f"https://github.com/{username}",
            })
            continue

        activity = profile.get("activity_score", 0)
        relevance = compute_relevance_score(profile, keywords)

        # Weighted combination: relevance matters more than raw activity
        combined = activity * 0.4 + relevance * 0.6

        strengths, gaps = generate_strengths_gaps(profile)

        # Build reasoning sentence
        parts = []
        if activity >= 120:
            parts.append("exceptional GitHub activity")
        elif activity >= 80:
            parts.append("strong GitHub activity")
        elif activity >= 40:
            parts.append("moderate GitHub activity")
        else:
            parts.append("limited public activity")

        if relevance >= 70:
            parts.append("high keyword match with job description")
        elif relevance >= 40:
            parts.append("partial keyword match")
        else:
            parts.append("low keyword overlap with job description")

        top_langs = profile.get("top_languages", [])[:3]
        if top_langs:
            parts.append(f"primary languages: {', '.join(top_langs)}")

        reasoning = ". ".join(p.capitalize() for p in parts) + "."

        candidates.append({
            "rank": 0,
            "username": username,
            "score": round(combined, 1),
            "reasoning": reasoning,
            "strengths": strengths,
            "gaps": gaps,
            "profile_url": profile.get("html_url", f"https://github.com/{username}"),
        })

    # Sort by score descending and assign ranks
    candidates.sort(key=lambda c: c["score"], reverse=True)
    for i, c in enumerate(candidates[:top_n], 1):
        c["rank"] = i

    payload = {
        "job_keywords_extracted": keywords[:20],
        "total_evaluated": len(candidates),
        "candidates": candidates[:top_n],
    }
    payload = _attach_offer(payload, "rank", payload["candidates"], profiles)
    return json.dumps(payload, indent=2)
