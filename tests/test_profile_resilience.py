"""A GitHub /search/* rate limit must not discard an otherwise complete profile."""

from __future__ import annotations

import json

import pytest

from github_talent_mcp.tools.profile import get_developer_profile


class _FakeClient:
    """Everything succeeds except the search endpoints, which 403 like the real
    ones do once the (much lower) search rate limit is exhausted."""

    def __init__(self, *, search_fails: bool = True):
        self.search_fails = search_fails

    async def get_user(self, username):
        return {
            "login": username, "name": "Octo Cat", "followers": 900, "following": 10,
            "public_repos": 40, "created_at": "2015-01-01T00:00:00Z",
            "avatar_url": "https://avatars.githubusercontent.com/u/1?v=4",
            "html_url": f"https://github.com/{username}", "bio": "Builds tools",
            "location": "San Francisco", "company": "@github", "blog": "",
            "twitter_username": None, "hireable": True, "email": None,
        }

    async def get_user_repos(self, username):
        return [{
            "name": "parcel", "description": "A bundler", "stargazers_count": 4000,
            "forks_count": 120, "language": "JavaScript", "fork": False,
            "license": {"spdx_id": "MIT"}, "topics": ["bundler"],
            "pushed_at": "2026-08-01T00:00:00Z", "owner": {"login": username},
        }]

    async def get_repo_languages(self, owner, repo):
        return {"JavaScript": 8000, "TypeScript": 2000}

    async def get_user_events(self, username, page=1):
        return []

    async def get_repo_info(self, owner, repo):
        return {"stargazers_count": 1000}

    async def get_profile_readme(self, username):
        return "# Hi"

    async def _search(self, *a, **k):
        if self.search_fails:
            raise RuntimeError("Client error '403 Forbidden' for url 'api.github.com/search/commits'")
        return 42

    search_commit_count = _search
    search_pr_count = _search


@pytest.mark.asyncio
async def test_search_403_still_yields_a_usable_profile():
    data = json.loads(await get_developer_profile(_FakeClient(), "octocat"))

    assert "error" not in data, "a search 403 discarded the whole profile"
    assert data["login"] == "octocat"
    assert data["avatar_url"].startswith("https://avatars.githubusercontent.com")
    assert data["top_languages"], "language data was lost"
    assert data["total_stars_received"] == 4000
    assert data["commits_last_90_days"] == 0, "unknown activity should read as 0"


@pytest.mark.asyncio
async def test_search_counts_are_used_when_the_endpoint_works():
    data = json.loads(await get_developer_profile(_FakeClient(search_fails=False), "octocat"))
    assert data["commits_last_90_days"] == 42
