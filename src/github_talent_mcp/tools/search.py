from __future__ import annotations

import json

from github_talent_mcp.github_client import GitHubClient


async def search_developers(
    client: GitHubClient,
    *,
    languages: list[str] | None = None,
    location: str | None = None,
    min_followers: int | None = None,
    min_repos: int | None = None,
    limit: int = 20,
) -> str:
    per_page = min(limit, 100)

    try:
        data = await client.search_users(
            languages=languages,
            location=location,
            min_followers=min_followers,
            min_repos=min_repos,
            per_page=per_page,
        )
    except Exception as e:
        return json.dumps({"error": f"GitHub API error: {e}"})

    results = []
    for item in data.get("items", [])[:limit]:
        results.append({
            "login": item["login"],
            "avatar_url": item.get("avatar_url", ""),
            "html_url": item.get("html_url", f"https://github.com/{item['login']}"),
        })

    return json.dumps({
        "total_count": data.get("total_count", 0),
        "returned": len(results),
        "note": "Use get_developer_profile on candidates for full enrichment with activity scoring.",
        "developers": results,
    }, indent=2)
