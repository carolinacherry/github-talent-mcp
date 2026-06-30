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
from github_talent_mcp.tools.score_jd import score_against_jd as _score_jd
from github_talent_mcp.tools.compare import compare_candidates as _compare
from github_talent_mcp.tools.bulk import bulk_score as _bulk
from github_talent_mcp.tools.outreach import generate_outreach as _outreach
from github_talent_mcp.tools.plan_search import plan_search as _plan_search

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
async def plan_search(request: str, job_description: str | None = None) -> str:
    """Plan a candidate search and surface follow-up questions BEFORE sourcing.

    Call this FIRST whenever the user asks to find, source, rank, or score
    candidates. It parses their request, detects the role family, and returns
    targeted follow-up questions plus what's still missing. Ask the user those
    questions — especially to paste the job description or share a public link to
    it — and wait for answers before calling search_developers, rank_candidates,
    or score_against_jd. Do not guess missing criteria.

    Args:
        request: The user's natural-language sourcing request, verbatim.
        job_description: The job description text, if the user already provided it.
    """
    return await _plan_search(request, job_description=job_description)


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

    Intake first — do not guess. Before searching, confirm the key criteria with
    the user if missing: languages, location (or remote/timezone), seniority, and
    2-4 must-have skills. If sourcing for a specific role, also ask the user to
    paste the job description or share a public link to it. Ask concise follow-up
    questions FIRST rather than firing a broad, low-signal search.

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

    Intake first — do not guess. Before calling, make sure you have the real job
    description: ask the user to paste the full JD text, or to share a public link
    to the posting and paste what it shows (you may not be able to open the link
    yourself). Also confirm target seniority, 2-4 must-have skills, location or
    remote/timezone, and any hard dealbreakers. If the request is missing these,
    ask concise follow-up questions FIRST, then call this tool.

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
async def score_against_jd(
    job_description: str,
    usernames: list[str],
    top_n: int = 10,
) -> str:
    """Score GitHub candidates against a job description with per-dimension breakdown.

    Unlike rank_candidates (keyword matching), this extracts structured requirements
    from the JD and scores each candidate on: tech stack match, experience level,
    OSS signal, and leadership signals. Returns dimension scores, gaps, and
    personalized interview questions.

    Intake first — do not guess. Before calling, make sure you have the real job
    description: ask the user to paste the full JD text, or to share a public link
    to the posting and paste what it shows (you may not be able to open the link
    yourself). Also confirm target seniority, 2-4 must-have skills, location or
    remote/timezone, and any hard dealbreakers. Ask concise follow-up questions
    FIRST if any are missing, then call this tool.

    Args:
        job_description: Full job description text
        usernames: GitHub usernames to evaluate
        top_n: Number of top candidates to return (default 10)
    """
    return await _score_jd(
        _get_client(),
        job_description=job_description,
        usernames=usernames,
        top_n=top_n,
    )


@mcp.tool()
async def compare_candidates(
    usernames: list[str],
    job_description: str | None = None,
) -> str:
    """Compare 2-5 GitHub candidates side-by-side.

    Shows each candidate's languages, activity, stars, strengths, and gaps.
    If a job description is provided, also scores each candidate against it
    and picks winners per dimension.

    Args:
        usernames: 2-5 GitHub usernames to compare
        job_description: Optional job description for JD-aware comparison
    """
    return await _compare(
        _get_client(),
        usernames=usernames,
        job_description=job_description,
    )


@mcp.tool()
async def bulk_score(
    usernames: list[str],
    job_description: str | None = None,
    export_format: str = "markdown",
    top_n: int = 100,
) -> str:
    """Score a batch of GitHub usernames and return a ranked table.

    Enriches each profile and ranks by activity score (or JD fit if a job
    description is provided). Returns a markdown table or CSV.

    Args:
        usernames: List of GitHub usernames (max 100)
        job_description: Optional JD for relevance scoring
        export_format: Output format - "markdown" (default) or "csv"
        top_n: Max candidates in output (default 100)
    """
    return await _bulk(
        _get_client(),
        usernames=usernames,
        job_description=job_description,
        export_format=export_format,
        top_n=top_n,
    )


@mcp.tool()
async def generate_outreach(
    username: str,
    job_description: str,
    company_name: str = "[Your Company]",
    sender_name: str = "[Your Name]",
    tone: str = "casual",
) -> str:
    """Generate personalized recruiter outreach messages for a GitHub candidate.

    Creates three message variants (short, medium, detailed) that reference
    the candidate's actual repos, contributions, and tech stack.

    IMPORTANT: Always ask the user for their company_name and sender_name
    before calling this tool. If not provided, placeholders will be used.

    Args:
        username: GitHub username of the candidate
        job_description: The role description
        company_name: Your company name (ask the user)
        sender_name: Your name as the recruiter/hiring manager (ask the user)
        tone: Message tone - "casual" (default) or "formal"
    """
    return await _outreach(
        _get_client(),
        username=username,
        job_description=job_description,
        company_name=company_name,
        sender_name=sender_name,
        tone=tone,
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
