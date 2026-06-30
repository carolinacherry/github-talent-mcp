import json

import pytest

from github_talent_mcp.tools.plan_search import plan_search


@pytest.mark.asyncio
async def test_asks_for_jd_and_detects_role_when_vague():
    out = json.loads(await plan_search("find me some security engineers"))
    assert out["ready_to_search"] is False
    assert "job_description" in out["missing"]
    assert any("job description" in q.lower() for q in out["follow_up_questions"])
    assert "security/IAM" in out["parsed"]["detected_roles"]


@pytest.mark.asyncio
async def test_extracts_signals_from_request_and_jd():
    out = json.loads(await plan_search(
        "Senior Rust engineer, remote",
        job_description="We need 5+ years building distributed systems.",
    ))
    p = out["parsed"]
    assert "rust" in p["languages"]
    assert "senior" in p["seniority_terms"]
    assert "remote" in p["location_signal"]
    assert p["has_job_description"] is True


@pytest.mark.asyncio
async def test_ready_when_all_criteria_present():
    out = json.loads(await plan_search(
        "Senior Go platform engineer, remote, must have Kubernetes",
        job_description="Full JD: own the platform, on-call, etc.",
    ))
    assert out["missing"] == []
    assert out["ready_to_search"] is True
    # dealbreakers question is always included
    assert any("dealbreaker" in q.lower() for q in out["follow_up_questions"])
