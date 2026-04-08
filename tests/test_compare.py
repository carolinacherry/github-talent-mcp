import json
from unittest.mock import AsyncMock, patch

import pytest

from github_talent_mcp.tools.compare import compare_candidates


def _mock_profile(username, **overrides):
    base = {
        "login": username,
        "name": username.title(),
        "html_url": f"https://github.com/{username}",
        "top_languages": ["Python"],
        "followers": 100,
        "total_stars_received": 50,
        "activity_score": 80,
        "commits_last_90_days": 20,
        "prs_opened_last_90_days": 5,
        "notable_repos": [{"name": "my-repo", "description": "A project", "language": "Python", "topics": [], "stars": 10}],
        "major_oss_contributions": [],
        "has_profile_readme": True,
        "repos_with_description_ratio": 0.7,
        "has_permissive_license_repos": True,
        "account_age_days": 2000,
        "bio": "Developer",
        "profile_readme_summary": "",
        "contributed_repo_stars": 0,
        "hireable": False,
    }
    base.update(overrides)
    return json.dumps(base)


@pytest.mark.asyncio
async def test_compare_two_candidates():
    client = AsyncMock()

    with patch("github_talent_mcp.tools.compare.get_developer_profile", new_callable=AsyncMock) as mock_profile:
        mock_profile.side_effect = [
            _mock_profile("alice", followers=500, total_stars_received=200),
            _mock_profile("bob", followers=50, total_stars_received=10),
        ]
        result = await compare_candidates(client, usernames=["alice", "bob"])

    data = json.loads(result)
    assert len(data["candidates"]) == 2
    assert data["candidates"][0]["username"] == "alice"
    assert data["candidates"][1]["username"] == "bob"
    assert "winners" in data
    assert data["winners"]["total_stars"] == "alice"


@pytest.mark.asyncio
async def test_compare_with_jd():
    client = AsyncMock()

    with patch("github_talent_mcp.tools.compare.get_developer_profile", new_callable=AsyncMock) as mock_profile:
        mock_profile.side_effect = [
            _mock_profile(
                "alice", top_languages=["Python", "Rust"], activity_score=150,
                followers=1000, total_stars_received=500, account_age_days=3000,
                notable_repos=[{"name": "fastapi-tool", "description": "FastAPI utils", "language": "Python", "topics": ["fastapi"], "stars": 100}],
            ),
            _mock_profile(
                "bob", top_languages=["Java"], activity_score=40,
                followers=10, total_stars_received=5,
            ),
        ]
        result = await compare_candidates(
            client, usernames=["alice", "bob"], job_description="Senior Python FastAPI engineer"
        )

    data = json.loads(result)
    assert "jd_overall_fit" in data["candidates"][0]
    assert "jd_dimensions" in data["candidates"][0]
    assert data["winners"]["overall_fit"] == "alice"
    assert len(data["recommendation"]) > 0


@pytest.mark.asyncio
async def test_compare_rejects_one_candidate():
    client = AsyncMock()
    result = await compare_candidates(client, usernames=["alice"])
    data = json.loads(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_compare_rejects_six_candidates():
    client = AsyncMock()
    result = await compare_candidates(client, usernames=["a", "b", "c", "d", "e", "f"])
    data = json.loads(result)
    assert "error" in data
