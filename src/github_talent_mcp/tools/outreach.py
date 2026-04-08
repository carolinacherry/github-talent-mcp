from __future__ import annotations

import json

from github_talent_mcp.github_client import GitHubClient
from github_talent_mcp.tools.profile import get_developer_profile


async def generate_outreach(
    client: GitHubClient,
    *,
    username: str,
    job_description: str,
    company_name: str = "[Your Company]",
    sender_name: str = "[Your Name]",
    tone: str = "casual",
) -> str:
    """Generate personalized recruiter outreach messages for a GitHub candidate."""
    if tone not in ("casual", "formal"):
        return json.dumps({"error": "tone must be 'casual' or 'formal'"})

    profile_json = await get_developer_profile(client, username)
    profile = json.loads(profile_json)

    if "error" in profile:
        return json.dumps({"error": f"Could not fetch profile: {profile['error']}"})

    name = profile.get("name") or username
    first_name = name.split()[0] if name else username
    repos = profile.get("notable_repos", [])
    languages = profile.get("top_languages", [])[:3]
    oss = profile.get("major_oss_contributions", [])[:2]
    stars = profile.get("total_stars_received", 0)

    # Pick the most interesting talking point (highest-starred repo)
    hook = ""
    valid_repos = [r for r in repos if isinstance(r, dict)]
    if valid_repos:
        top_repo = max(valid_repos, key=lambda r: r.get("stars", 0))
        repo_name = top_repo.get("name", "")
        repo_stars = top_repo.get("stars", 0)
        repo_desc = top_repo.get("description", "")
        if repo_stars >= 100:
            hook = f"your work on {repo_name} ({repo_stars:,} stars)"
        elif repo_desc:
            hook = f"your project {repo_name}"
        else:
            hook = f"{repo_name}"

    if not hook and oss:
        hook = f"your contributions to {oss[0]}"
    if not hook and languages:
        hook = f"your {languages[0]} work on GitHub"
    if not hook:
        hook = "your GitHub profile"

    lang_str = " and ".join(languages[:2]) if languages else "your tech stack"

    # Generate three variants
    if tone == "casual":
        short = (
            f"Hey {first_name} -- saw {hook} and thought you'd be a great fit "
            f"for a role we're hiring for at {company_name}. "
            f"Would you be open to a quick chat?\n\n"
            f"-- {sender_name}"
        )
        medium = (
            f"Hi {first_name},\n\n"
            f"I came across {hook} and was impressed. "
            f"We're building something at {company_name} that aligns with "
            f"your {lang_str} experience.\n\n"
            f"Here's the gist: {job_description[:150].strip()}...\n\n"
            f"No pressure, but would love to tell you more if you're curious.\n\n"
            f"-- {sender_name}"
        )
        detailed = (
            f"Hi {first_name},\n\n"
            f"I've been looking at {hook} -- "
            f"{'really solid work. ' if stars >= 50 else ''}"
            f"{'Your contributions to ' + ', '.join(oss[:2]) + ' also stand out. ' if oss else ''}\n\n"
            f"I'm {sender_name} at {company_name}. We're hiring for a role "
            f"that I think matches your background well:\n\n"
            f"{job_description[:300].strip()}\n\n"
            f"Your {lang_str} experience and "
            f"{'track record in open source' if oss else 'GitHub activity'} "
            f"are exactly what we're looking for.\n\n"
            f"Would you be up for a 15-minute call this week? "
            f"Happy to share more details either way.\n\n"
            f"Best,\n{sender_name}"
        )
    else:
        short = (
            f"Dear {name},\n\n"
            f"I noticed {hook} and believe your experience would be "
            f"an excellent fit for a position at {company_name}. "
            f"Would you be available for a brief conversation?\n\n"
            f"Best regards,\n{sender_name}"
        )
        medium = (
            f"Dear {name},\n\n"
            f"I came across your GitHub profile, particularly {hook}. "
            f"Your expertise in {lang_str} aligns well with a role we are "
            f"currently hiring for at {company_name}.\n\n"
            f"The position involves: {job_description[:150].strip()}...\n\n"
            f"I would welcome the opportunity to discuss this further "
            f"at your convenience.\n\n"
            f"Best regards,\n{sender_name}"
        )
        detailed = (
            f"Dear {name},\n\n"
            f"I have been following {hook} with great interest"
            f"{', as well as your contributions to ' + ', '.join(oss[:2]) if oss else ''}. "
            f"Your work demonstrates the caliber of engineering we seek at {company_name}.\n\n"
            f"We are currently hiring for the following role:\n\n"
            f"{job_description[:300].strip()}\n\n"
            f"Given your {lang_str} expertise and "
            f"{'demonstrated commitment to open source' if oss else 'technical background'}, "
            f"I believe this could be an excellent mutual fit.\n\n"
            f"Would you be open to a brief introductory call? "
            f"I am happy to provide additional details about the role and team.\n\n"
            f"Kind regards,\n{sender_name}"
        )

    return json.dumps({
        "candidate": {
            "username": username,
            "name": name,
            "profile_url": profile.get("html_url", f"https://github.com/{username}"),
            "hook_used": hook,
        },
        "messages": {
            "short": short,
            "medium": medium,
            "detailed": detailed,
        },
        "tone": tone,
    }, indent=2)
