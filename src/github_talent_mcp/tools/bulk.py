from __future__ import annotations

import json

from github_talent_mcp.github_client import GitHubClient
from github_talent_mcp.scoring import score_jd_dimensions, generate_strengths_gaps
from github_talent_mcp.tools.profile import enrich_profiles


async def bulk_score(
    client: GitHubClient,
    *,
    usernames: list[str],
    job_description: str | None = None,
    export_format: str = "markdown",
    top_n: int = 100,
) -> str:
    """Score a batch of GitHub usernames and return a ranked table."""
    if len(usernames) > 100:
        return json.dumps({"error": "Max 100 usernames per batch"})
    if len(usernames) == 0:
        return json.dumps({"error": "No usernames provided"})

    # Estimate API cost upfront
    estimated_calls = len(usernames) * 8  # ~8 API calls per profile
    rows = []
    errors = []

    profiles = await enrich_profiles(client, usernames)
    for username in usernames:
        profile = profiles[username]

        if "error" in profile:
            errors.append({"username": username, "error": profile["error"]})
            continue

        row: dict = {
            "username": username,
            "name": profile.get("name") or username,
            "languages": ", ".join(profile.get("top_languages", [])[:3]),
            "activity_score": profile.get("activity_score", 0),
            "stars": profile.get("total_stars_received", 0),
            "followers": profile.get("followers", 0),
            "commits_90d": profile.get("commits_last_90_days", 0),
        }

        if job_description:
            jd_scores = score_jd_dimensions(profile, job_description)
            row["jd_fit"] = jd_scores["overall_fit"]
            row["tech_match"] = jd_scores["dimensions"]["tech_stack_match"]
        else:
            row["jd_fit"] = None
            row["tech_match"] = None

        strengths, gaps = generate_strengths_gaps(profile)
        row["key_signal"] = strengths[0] if strengths else (gaps[0] if gaps else "")

        rows.append(row)

    # Sort by jd_fit if available, otherwise activity_score
    sort_key = "jd_fit" if job_description else "activity_score"
    rows.sort(key=lambda r: r.get(sort_key) or 0, reverse=True)

    # Assign ranks
    for i, row in enumerate(rows[:top_n], 1):
        row["rank"] = i

    rows = rows[:top_n]

    if export_format == "csv":
        output = _to_csv(rows, has_jd=bool(job_description))
    else:
        output = _to_markdown(rows, has_jd=bool(job_description))

    return json.dumps({
        "format": export_format,
        "total_scored": len(rows),
        "total_errors": len(errors),
        "estimated_api_calls": estimated_calls,
        "errors": errors[:5],
        "table": output,
    }, indent=2)


def _to_markdown(rows: list[dict], *, has_jd: bool) -> str:
    if not rows:
        return "No candidates scored."

    if has_jd:
        header = "| # | Username | Name | Languages | JD Fit | Tech | Activity | Stars | Key Signal |"
        sep = "|---|----------|------|-----------|--------|------|----------|-------|------------|"
        lines = [header, sep]
        for r in rows:
            lines.append(
                f"| {r['rank']} | [{r['username']}](https://github.com/{r['username']}) "
                f"| {r['name']} | {r['languages']} | {r['jd_fit']} | {r['tech_match']} "
                f"| {r['activity_score']} | {r['stars']} | {r['key_signal'][:60]} |"
            )
    else:
        header = "| # | Username | Name | Languages | Activity | Stars | Commits 90d | Key Signal |"
        sep = "|---|----------|------|-----------|----------|-------|-------------|------------|"
        lines = [header, sep]
        for r in rows:
            lines.append(
                f"| {r['rank']} | [{r['username']}](https://github.com/{r['username']}) "
                f"| {r['name']} | {r['languages']} | {r['activity_score']} "
                f"| {r['stars']} | {r['commits_90d']} | {r['key_signal'][:60]} |"
            )

    return "\n".join(lines)


def _to_csv(rows: list[dict], *, has_jd: bool) -> str:
    if not rows:
        return ""

    if has_jd:
        header = "rank,username,name,languages,jd_fit,tech_match,activity_score,stars,key_signal"
        lines = [header]
        for r in rows:
            signal = r["key_signal"].replace('"', '""')[:60]
            lines.append(
                f"{r['rank']},{r['username']},\"{r['name']}\",\"{r['languages']}\","
                f"{r['jd_fit']},{r['tech_match']},{r['activity_score']},{r['stars']},\"{signal}\""
            )
    else:
        header = "rank,username,name,languages,activity_score,stars,commits_90d,key_signal"
        lines = [header]
        for r in rows:
            signal = r["key_signal"].replace('"', '""')[:60]
            lines.append(
                f"{r['rank']},{r['username']},\"{r['name']}\",\"{r['languages']}\","
                f"{r['activity_score']},{r['stars']},{r['commits_90d']},\"{signal}\""
            )

    return "\n".join(lines)
