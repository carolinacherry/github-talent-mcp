from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from github_talent_mcp.github_client import GitHubClient
from github_talent_mcp.tools.search import search_developers as _search
from github_talent_mcp.tools.profile import get_developer_profile as _profile
from github_talent_mcp.tools.rank import rank_candidates as _rank
from github_talent_mcp.tools.contributors import get_repo_contributors as _contributors

load_dotenv()

logging.basicConfig(level=logging.INFO, stream=sys.stderr)

mcp = FastMCP("github-talent")

_client: GitHubClient | None = None


def _get_client() -> GitHubClient:
    global _client
    if _client is None:
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            logging.warning("GITHUB_TOKEN not set — API requests limited to 60/hr")
        _client = GitHubClient(token=token)
    return _client


@mcp.tool()
async def search_developers(
    languages: list[str] | None = None,
    location: str | None = None,
    min_followers: int | None = None,
    min_repos: int | None = None,
    limit: int = 20,
) -> str:
    """Search GitHub developers by technical and geographic filters.

    Returns a list of matching usernames sorted by followers. Use
    get_developer_profile on interesting candidates for full enrichment
    and to verify recent activity.

    For topic-based sourcing (e.g. "LLM", "inference"), use get_repo_contributors
    on relevant repos instead — GitHub user search doesn't support topic/bio search.

    Args:
        languages: Filter by programming languages, e.g. ["python", "rust"]
        location: Filter by location, e.g. "San Francisco" or "Germany"
        min_followers: Minimum follower count
        min_repos: Minimum public repo count
        limit: Max results to return (default 20, max 100)
    """
    return await _search(
        _get_client(),
        languages=languages,
        location=location,
        min_followers=min_followers,
        min_repos=min_repos,
        limit=limit,
    )


@mcp.tool()
async def get_developer_profile(username: str) -> str:
    """Get enriched GitHub developer profile with activity scoring.

    Returns languages, stars, commit activity, OSS contributions, profile README,
    license breakdown, and a 0-205 activity score with per-dimension breakdown.

    Args:
        username: GitHub username to analyze
    """
    return await _profile(_get_client(), username)


@mcp.tool()
async def rank_candidates(
    usernames: list[str],
    job_description: str,
    top_n: int = 10,
) -> str:
    """Rank GitHub users against a job description.

    Enriches each profile, scores activity + relevance, and returns candidates
    sorted by combined score with strengths, gaps, and reasoning.

    Args:
        usernames: GitHub usernames to evaluate
        job_description: The role description to rank candidates against
        top_n: Number of top candidates to return (default 10)
    """
    return await _rank(
        _get_client(),
        usernames=usernames,
        job_description=job_description,
        top_n=top_n,
    )


@mcp.tool()
async def get_repo_contributors(
    repo: str,
    limit: int = 25,
) -> str:
    """Get top contributors for a GitHub repository as candidate leads.

    Accepts 'owner/repo' format or full GitHub URL.

    Args:
        repo: Repository in 'owner/repo' format or GitHub URL
        limit: Max contributors to return (default 25)
    """
    return await _contributors(_get_client(), repo=repo, limit=limit)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
