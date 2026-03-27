from __future__ import annotations

from pydantic import BaseModel, Field


class DeveloperSearchResult(BaseModel):
    login: str
    name: str | None = None
    avatar_url: str
    html_url: str
    type: str = "User"


class NotableRepo(BaseModel):
    name: str
    description: str | None = None
    stars: int = 0
    forks: int = 0
    language: str | None = None
    license: str | None = None
    topics: list[str] = Field(default_factory=list)
    last_updated: str | None = None


class DeveloperProfile(BaseModel):
    login: str
    name: str | None = None
    bio: str | None = None
    location: str | None = None
    email: str | None = None
    blog: str | None = None
    company: str | None = None
    twitter_username: str | None = None
    hireable: bool | None = None
    followers: int = 0
    following: int = 0
    public_repos: int = 0
    account_age_days: int = 0
    avatar_url: str = ""
    html_url: str = ""

    # Profile README
    has_profile_readme: bool = False
    profile_readme_length: int = 0
    profile_readme_summary: str | None = None

    # Language analysis
    top_languages: list[str] = Field(default_factory=list)
    language_breakdown: dict[str, float] = Field(default_factory=dict)

    # Repo metrics
    total_stars_received: int = 0
    total_forks_received: int = 0
    notable_repos: list[NotableRepo] = Field(default_factory=list)
    repos_with_description_ratio: float = 0.0

    # License analysis
    open_source_license_ratio: float = 0.0
    license_breakdown: dict[str, int] = Field(default_factory=dict)
    has_permissive_license_repos: bool = False

    # Activity
    commits_last_30_days: int = 0
    commits_last_90_days: int = 0
    prs_opened_last_30_days: int = 0
    prs_opened_last_90_days: int = 0
    contributed_repo_stars: int = 0
    last_active: str | None = None

    # OSS contributions
    contributes_to_major_oss: bool = False
    major_oss_contributions: list[str] = Field(default_factory=list)

    # Linked profiles
    linked_profiles: dict[str, str | None] = Field(default_factory=dict)

    # Scoring
    activity_score: int = 0
    activity_score_breakdown: dict[str, int] = Field(default_factory=dict)


class RankedCandidate(BaseModel):
    rank: int
    username: str
    score: float
    reasoning: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    profile_url: str


class RepoContributor(BaseModel):
    login: str
    contributions: int
    html_url: str
    avatar_url: str = ""
