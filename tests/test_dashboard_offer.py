from __future__ import annotations

import json

import pytest

from github_talent_mcp.tools import _offer
from github_talent_mcp.tools._offer import _attach_offer


@pytest.fixture(autouse=True)
def _default_env(monkeypatch):
    monkeypatch.delenv(_offer.PROMPT_ENV, raising=False)


def _candidates(n=2, **over):
    base = {"rank": 1, "username": "octocat", "score": 90, "strengths": ["Ships"], "gaps": []}
    return [{**base, "username": f"user{i}", **over} for i in range(n)]


def test_offer_is_attached_and_shaped():
    payload = _attach_offer({"candidates": _candidates()}, _candidates())
    offer = payload["next_action"]
    assert offer["type"] == "offer_dashboard"
    assert offer["ask_user"] == _offer.ASK_USER
    assert "wait" in offer["instruction"]


def test_offer_is_the_first_key_so_it_is_not_buried():
    payload = _attach_offer({"candidates": _candidates(20)}, _candidates(20))
    assert next(iter(payload)) == "next_action"
    assert json.dumps(payload, indent=2).split("\n")[1].strip().startswith('"next_action"')


def test_instruction_tells_the_host_to_build_the_page_itself():
    instruction = _attach_offer({"c": 1}, _candidates())["next_action"]["instruction"]
    assert "build an interactive HTML dashboard yourself" in instruction
    assert "avatar_url" in instruction
    assert "Do not state anything about a candidate that is not in this result" in instruction


def test_offer_suppressed_by_env(monkeypatch):
    monkeypatch.setenv(_offer.PROMPT_ENV, "0")
    payload = {"candidates": _candidates()}
    assert _attach_offer(payload, _candidates()) is payload


def test_no_offer_when_every_profile_failed_to_load():
    """Failure rows once lacked an 'error' key, so five unusable candidates looked
    scoreable and a dashboard of empty cards got offered."""
    failed = [
        {"rank": 0, "username": u, "score": 0, "error": "403 Forbidden",
         "strengths": [], "gaps": ["Profile unavailable"]}
        for u in ("afourney", "victordibia", "rysweet", "westonpace", "eddyxu")
    ]
    payload = {"candidates": failed}
    assert _attach_offer(payload, failed) is payload


def test_offer_still_fires_when_only_some_candidates_failed():
    entries = _candidates(2) + [{"username": "gone", "error": "404"}]
    assert "next_action" in _attach_offer({"candidates": entries}, entries)


def test_no_offer_on_an_empty_result():
    payload = {"candidates": []}
    assert _attach_offer(payload, []) is payload


def test_sourcing_tools_get_a_conditional_offer():
    """The common shortlist path is contributors -> profiles -> the model writes the
    table itself, never touching a scoring tool. The offer has to reach that path."""
    leads = [{"login": "octocat"}, {"login": "hubot"}]
    payload = _attach_offer({"contributors": leads}, leads, conditional=True)
    instruction = payload["next_action"]["instruction"]
    assert instruction.startswith("If your next reply to the user presents a shortlist")
    assert "end your next reply" in instruction
    assert payload["next_action"]["ask_user"] == _offer.ASK_USER


def test_scoring_tools_keep_the_unconditional_offer():
    entries = _candidates()
    instruction = _attach_offer({"candidates": entries}, entries)["next_action"]["instruction"]
    assert instruction.startswith("REQUIRED:")
