from __future__ import annotations

import json
from urllib.parse import urlparse

from github_talent_mcp.github_client import GitHubClient


def parse_repo_string(repo: str) -> tuple[str, str]:
    """Parse 'owner/repo', 'https://github.com/owner/repo', or 'github.com/owner/repo' into (owner, repo)."""
    repo = repo.strip().rstrip("/")

    # Handle URLs
    if "github.com" in repo:
        parsed = urlparse(repo if "://" in repo else f"https://{repo}")
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2:
            return parts[0], parts[1]
        raise ValueError(f"Could not parse owner/repo from URL: {repo}")

    # Handle owner/repo
    if "/" in repo:
        parts = repo.split("/")
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]

    raise ValueError(f"Expected 'owner/repo' or GitHub URL, got: {repo}")


async def get_repo_contributors(
    client: GitHubClient,
    *,
    repo: str,
    limit: int = 25,
) -> str:
    try:
        owner, repo_name = parse_repo_string(repo)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    try:
        data = await client.get_repo_contributors(owner, repo_name, per_page=min(limit, 100))
    except Exception as e:
        return json.dumps({"error": f"GitHub API error: {e}"})

    contributors = []
    for c in data[:limit]:
        if c.get("type") != "User":
            continue
        contributors.append({
            "login": c["login"],
            "contributions": c["contributions"],
            "html_url": f"https://github.com/{c['login']}",
            "avatar_url": c.get("avatar_url", ""),
        })

    return json.dumps({
        "repo": f"{owner}/{repo_name}",
        "total_returned": len(contributors),
        "contributors": contributors,
    }, indent=2)
