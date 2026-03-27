from github_talent_mcp.scoring import (
    _compute_reputation_floor,
    compute_activity_score,
    compute_relevance_score,
    extract_keywords,
    generate_strengths_gaps,
)


def test_activity_score_max():
    profile = {
        "commits_last_90_days": 100,
        "has_profile_readme": True,
        "total_stars_received": 500,
        "followers": 50,
        "repos_with_description_ratio": 1.0,
        "has_permissive_license_repos": True,
        "major_oss_contributions": ["a/b", "c/d", "e/f"],
    }
    score, breakdown = compute_activity_score(profile)
    assert score == 205
    assert breakdown["commits_last_90_days"] == 60
    assert breakdown["has_profile_readme"] == 20
    assert breakdown["stars_on_own_repos"] == 40
    assert breakdown["followers"] == 20
    assert breakdown["repos_with_description"] == 20
    assert breakdown["permissive_license_repos"] == 15
    assert breakdown["major_oss_contributions"] == 30


def test_activity_score_zero():
    score, breakdown = compute_activity_score({})
    assert score == 0
    assert all(v == 0 for v in breakdown.values())


def test_activity_score_partial():
    profile = {
        "commits_last_90_days": 5,
        "has_profile_readme": True,
        "total_stars_received": 3,
        "followers": 10,
        "repos_with_description_ratio": 0.5,
        "has_permissive_license_repos": False,
        "major_oss_contributions": [],
    }
    score, breakdown = compute_activity_score(profile)
    expected = 15 + 20 + 6 + 10 + 10 + 0 + 0
    assert score == expected


def test_activity_score_caps():
    """Each dimension should cap, not overflow."""
    profile = {
        "commits_last_90_days": 1000,
        "total_stars_received": 10000,
        "followers": 500,
        "major_oss_contributions": ["a", "b", "c", "d", "e"],
    }
    score, breakdown = compute_activity_score(profile)
    assert breakdown["commits_last_90_days"] == 60
    assert breakdown["stars_on_own_repos"] == 40
    assert breakdown["followers"] == 20
    assert breakdown["major_oss_contributions"] == 30


def test_activity_score_with_prs_and_contributed_stars():
    """PRs and contributed repo stars should boost the score."""
    # This simulates what profile.py feeds into scoring:
    # total_activity_90d = commits_90d + (prs_opened_90d * 3)
    # combined_stars = personal_stars + contributed_stars
    profile = {
        "commits_last_90_days": 75,  # profile.py passes total_activity_90d here
        "has_profile_readme": False,
        "total_stars_received": 50000,  # profile.py passes combined_stars here
        "followers": 500,
        "repos_with_description_ratio": 0.5,
        "has_permissive_license_repos": False,
        "major_oss_contributions": ["vllm-project/vllm"],
    }
    score, breakdown = compute_activity_score(profile)
    assert breakdown["commits_last_90_days"] == 60  # 75 * 3 = 225, capped at 60
    assert breakdown["stars_on_own_repos"] == 40  # 50000 * 2 capped at 40
    assert breakdown["followers"] == 20  # 500 capped at 20
    # Behavioral = 140 (60+0+40+20+10+0+10), but 50K stars triggers 150 reputation floor
    assert score == 150


def test_reputation_floor_thresholds():
    assert _compute_reputation_floor(10_000, 0, 0) == 150
    assert _compute_reputation_floor(0, 50_000, 0) == 150
    assert _compute_reputation_floor(1_000, 0, 0) == 120
    assert _compute_reputation_floor(0, 5_000, 0) == 120
    assert _compute_reputation_floor(500, 0, 0) == 100
    assert _compute_reputation_floor(0, 1_000, 0) == 100
    assert _compute_reputation_floor(100, 0, 0) == 80
    assert _compute_reputation_floor(0, 200, 0) == 80
    assert _compute_reputation_floor(50, 100, 0) == 0


def test_reputation_floor_torvalds_scenario():
    """Torvalds: 293K followers, 235K stars, zero recent commits. Should score >= 150."""
    profile = {
        "commits_last_90_days": 0,
        "has_profile_readme": False,
        "total_stars_received": 235_000,
        "followers": 293_000,
        "repos_with_description_ratio": 1.0,
        "has_permissive_license_repos": False,
        "major_oss_contributions": [],
        "account_age_days": 5300,
    }
    score, breakdown = compute_activity_score(profile)
    assert score >= 150
    assert "reputation_floor" in breakdown


def test_reputation_floor_does_not_lower_high_behavioral():
    """If behavioral score is already high, floor doesn't cap it down."""
    profile = {
        "commits_last_90_days": 100,
        "has_profile_readme": True,
        "total_stars_received": 500,
        "followers": 50,
        "repos_with_description_ratio": 1.0,
        "has_permissive_license_repos": True,
        "major_oss_contributions": ["a/b", "c/d", "e/f"],
    }
    score, breakdown = compute_activity_score(profile)
    assert score == 205
    assert "reputation_floor" not in breakdown


def test_extract_keywords():
    jd = "Senior Python engineer with experience in Rust and distributed systems"
    keywords = extract_keywords(jd)
    assert "python" in keywords
    assert "rust" in keywords
    assert "distributed" in keywords
    assert "systems" in keywords
    # Noise words filtered
    assert "with" not in keywords
    assert "and" not in keywords
    assert "in" not in keywords


def test_extract_keywords_preserves_special():
    """C++, C#, .NET should survive."""
    keywords = extract_keywords("C++ and C# and .NET developer")
    assert "c++" in keywords
    assert "c#" in keywords
    assert ".net" in keywords


def test_extract_keywords_dedupes():
    keywords = extract_keywords("python Python PYTHON")
    assert keywords.count("python") == 1


def test_relevance_score_full_match():
    profile = {
        "bio": "Python and Rust developer",
        "top_languages": ["Python", "Rust"],
        "major_oss_contributions": [],
        "notable_repos": [],
        "profile_readme_summary": "",
    }
    score = compute_relevance_score(profile, ["python", "rust"])
    assert score == 100


def test_relevance_score_no_match():
    profile = {
        "bio": "Java developer",
        "top_languages": ["Java"],
        "major_oss_contributions": [],
        "notable_repos": [],
    }
    score = compute_relevance_score(profile, ["python", "rust", "cuda"])
    assert score == 0


def test_relevance_score_no_keywords():
    score = compute_relevance_score({}, [])
    assert score == 50


def test_strengths_gaps_active():
    profile = {
        "commits_last_90_days": 50,
        "has_profile_readme": True,
        "total_stars_received": 100,
        "major_oss_contributions": ["facebook/react"],
        "has_permissive_license_repos": True,
        "followers": 200,
        "hireable": True,
        "top_languages": ["TypeScript", "Python"],
    }
    strengths, gaps = generate_strengths_gaps(profile)
    assert len(strengths) >= 4
    assert len(gaps) == 0


def test_strengths_gaps_inactive():
    profile = {
        "commits_last_90_days": 0,
        "prs_opened_last_90_days": 0,
        "has_profile_readme": False,
        "total_stars_received": 0,
        "contributed_repo_stars": 0,
        "major_oss_contributions": [],
        "has_permissive_license_repos": False,
        "followers": 2,
        "top_languages": [],
    }
    strengths, gaps = generate_strengths_gaps(profile)
    assert len(gaps) >= 3
    assert len(strengths) == 0


def test_strengths_pr_based_workflow():
    """PR-heavy contributor (like org repo maintainers) gets activity credit."""
    profile = {
        "commits_last_90_days": 0,
        "prs_opened_last_90_days": 25,
        "has_profile_readme": False,
        "total_stars_received": 0,
        "contributed_repo_stars": 50000,
        "major_oss_contributions": ["vllm-project/vllm"],
        "has_permissive_license_repos": False,
        "followers": 500,
        "hireable": False,
        "top_languages": ["Python", "C++"],
    }
    strengths, gaps = generate_strengths_gaps(profile)
    assert any("PR" in s for s in strengths)
    assert any("50,000" in s for s in strengths)
