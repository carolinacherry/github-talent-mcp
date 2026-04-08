from github_talent_mcp.scoring import score_jd_dimensions


def _make_profile(**overrides):
    base = {
        "top_languages": ["Python", "TypeScript"],
        "notable_repos": [
            {"name": "my-project", "description": "An API server", "language": "Python",
             "topics": ["fastapi", "rest"], "stars": 50},
        ],
        "profile_readme_summary": "ML engineer building tools",
        "total_stars_received": 200,
        "followers": 150,
        "account_age_days": 2000,
        "activity_score": 100,
        "major_oss_contributions": ["org/repo"],
        "has_profile_readme": True,
        "repos_with_description_ratio": 0.8,
        "has_permissive_license_repos": True,
        "bio": "Staff engineer at startup",
        "company": "Acme Inc",
    }
    base.update(overrides)
    return base


def test_strong_match():
    profile = _make_profile()
    jd = "Senior Python engineer with FastAPI experience. Must have open source contributions."
    result = score_jd_dimensions(profile, jd)

    assert result["overall_fit"] >= 60
    assert result["dimensions"]["tech_stack_match"] >= 50
    assert result["required_level"] == "senior"
    assert isinstance(result["gaps"], list)
    assert isinstance(result["interview_questions"], list)


def test_tech_mismatch():
    profile = _make_profile(top_languages=["Java", "Scala"], notable_repos=[])
    jd = "Senior Rust and CUDA engineer for GPU computing"
    result = score_jd_dimensions(profile, jd)

    assert result["dimensions"]["tech_stack_match"] < 30
    assert any("Missing from profile" in g for g in result["gaps"])


def test_junior_for_senior_role():
    profile = _make_profile(
        followers=5,
        total_stars_received=2,
        account_age_days=200,
        major_oss_contributions=[],
        activity_score=20,
    )
    jd = "Staff engineer to lead platform team"
    result = score_jd_dimensions(profile, jd)

    assert result["dimensions"]["experience_level"] < 50
    assert result["estimated_candidate_level"] == "junior"


def test_no_tech_requirements():
    """JD with no specific tech should give neutral tech score."""
    profile = _make_profile()
    jd = "Looking for a senior engineering manager to lead the team"
    result = score_jd_dimensions(profile, jd)

    assert result["dimensions"]["tech_stack_match"] == 50


def test_interview_questions_generated():
    profile = _make_profile()
    jd = "Senior Python engineer"
    result = score_jd_dimensions(profile, jd)

    assert len(result["interview_questions"]) >= 1
    assert len(result["interview_questions"]) <= 3


def test_unknown_level():
    """JD without seniority terms should give neutral experience score."""
    profile = _make_profile()
    jd = "Python engineer for data pipeline work"
    result = score_jd_dimensions(profile, jd)

    assert result["required_level"] == "unknown"
    assert result["dimensions"]["experience_level"] == 60
