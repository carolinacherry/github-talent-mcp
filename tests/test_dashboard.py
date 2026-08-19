from __future__ import annotations

import json
from pathlib import Path

import pytest

from github_talent_mcp import dashboard


def _read(path) -> str:
    return Path(path).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch, tmp_path):
    dashboard._cache.clear()
    monkeypatch.setenv(dashboard.DIR_ENV, str(tmp_path))
    monkeypatch.delenv(dashboard.PROMPT_ENV, raising=False)


def _profile(login="octocat", **over):
    base = {
        "login": login,
        "name": "Octo Cat",
        "bio": "Builds developer tools",
        "location": "San Francisco",
        "company": "@github",
        "hireable": True,
        "avatar_url": "https://avatars.githubusercontent.com/u/1?v=4",
        "html_url": f"https://github.com/{login}",
        "top_languages": ["TypeScript", "Rust"],
        "total_stars_received": 1200,
        "followers": 900,
        "commits_last_90_days": 140,
        "activity_score": 150,
        "major_oss_contributions": ["facebook/react"],
        "notable_repos": [
            {"name": "parcel", "stars": 40000, "language": "JavaScript", "topics": ["bundler"]},
        ],
    }
    base.update(over)
    return base


def _rank_payload():
    return {
        "total_evaluated": 1,
        "candidates": [{
            "rank": 1,
            "username": "octocat",
            "score": 118.4,
            "reasoning": "Exceptional GitHub activity.",
            "strengths": ["6.8k stars across public repos"],
            "gaps": ["No Go experience"],
            "profile_url": "https://github.com/octocat",
        }],
    }


def test_offer_is_attached_and_shaped():
    rid = dashboard.register_result("rank", _rank_payload(), {"octocat": _profile()})
    offer = dashboard.next_action(rid, 1)
    assert offer["type"] == "offer_dashboard"
    assert offer["result_id"] == rid
    assert offer["ask_user"] == dashboard.ASK_USER
    assert "wait" in offer["instruction"].lower()


def test_offer_suppressed_by_env(monkeypatch):
    monkeypatch.setenv(dashboard.PROMPT_ENV, "0")
    assert dashboard.next_action("rank-0001", 5) is None


def test_offer_suppressed_when_no_candidates():
    assert dashboard.next_action("rank-0001", 0) is None


def test_build_round_trips_from_cache():
    rid = dashboard.register_result("rank", _rank_payload(), {"octocat": _profile()})
    result = dashboard.build(rid, title="Staff Design Engineer candidates")
    assert result["candidate_count"] == 1
    assert result["file_url"].startswith("file://")
    html = _read(result["path"])
    assert "Staff Design Engineer candidates" in html
    assert "6.8k stars across public repos" in html


def test_unknown_result_id_is_a_clear_error():
    result = dashboard.build("rank-9999")
    assert "error" in result
    assert "restarted" in result["error"]


def test_cache_is_bounded():
    for _ in range(dashboard._MAX_CACHED + 8):
        dashboard.register_result("rank", _rank_payload(), {})
    assert len(dashboard._cache) == dashboard._MAX_CACHED


def test_cached_payload_is_not_mutated_by_caller():
    payload = _rank_payload()
    rid = dashboard.register_result("rank", payload, {})
    payload["next_action"] = {"type": "offer_dashboard"}
    assert "next_action" not in dashboard._cache[rid]["payload"]


def test_hostile_candidate_data_cannot_break_out_of_the_script_block():
    payload = {
        "candidates": [{
            "rank": 1,
            "username": "evil",
            "score": 10,
            "reasoning": "</script><img src=x onerror=alert(1)>",
            "strengths": ["<svg/onload=alert(2)>"],
            "gaps": [],
            "profile_url": "https://github.com/evil",
        }],
    }
    profiles = {"evil": _profile("evil", bio="</script><script>alert(3)</script>")}
    rid = dashboard.register_result("rank", payload, profiles)
    html = _read(dashboard.build(rid)["path"])

    assert "</script><img" not in html
    assert "<svg/onload" not in html
    assert "alert(3)</script>" not in html
    assert "\\u003c/script\\u003e" in html
    # exactly the two script tags the template itself opens
    assert html.count("<script") == 2


def test_non_github_links_are_replaced_with_the_canonical_profile():
    payload = {
        "candidates": [{
            "rank": 1,
            "username": "evil",
            "score": 10,
            "strengths": [],
            "gaps": [],
            "profile_url": "javascript:alert(1)",
        }],
    }
    rid = dashboard.register_result("rank", payload, {"evil": _profile("evil", html_url="http://phish.example")})
    html = _read(dashboard.build(rid)["path"])
    assert "javascript:alert" not in html
    assert "phish.example" not in html
    assert "https://github.com/evil" in html


def test_csp_image_policy_tracks_the_avatar_setting():
    rid = dashboard.register_result("rank", _rank_payload(), {"octocat": _profile()})
    html = _read(dashboard.build(rid)["path"])
    assert "img-src https://avatars.githubusercontent.com data:;" in html
    assert '"includeAvatars": true' in html

    rid2 = dashboard.register_result("rank", _rank_payload(), {"octocat": _profile()})
    html2 = _read(dashboard.build(rid2, include_avatars=False)["path"])
    assert "img-src 'none';" in html2
    assert '"includeAvatars": false' in html2


def test_open_in_browser_is_off_unless_asked(monkeypatch):
    calls = []
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda url: calls.append(url) or True)

    rid = dashboard.register_result("rank", _rank_payload(), {"octocat": _profile()})
    assert dashboard.build(rid)["opened_in_browser"] is False
    assert calls == []

    rid2 = dashboard.register_result("rank", _rank_payload(), {"octocat": _profile()})
    result = dashboard.build(rid2, open_in_browser=True)
    assert result["opened_in_browser"] is True
    assert calls == [result["file_url"]]


def test_page_carries_its_own_open_in_browser_link():
    rid = dashboard.register_result("rank", _rank_payload(), {"octocat": _profile()})
    html = _read(dashboard.build(rid)["path"])
    assert 'id="openbtn"' in html
    assert "Open in browser" in html


def test_avatar_url_from_another_host_is_dropped():
    profile = _profile(avatar_url="https://tracker.example/pixel.gif")
    rid = dashboard.register_result("rank", _rank_payload(), {"octocat": profile})
    html = _read(dashboard.build(rid)["path"])
    assert "tracker.example" not in html


def test_title_cannot_escape_the_dashboard_directory(tmp_path):
    rid = dashboard.register_result("rank", _rank_payload(), {"octocat": _profile()})
    result = dashboard.build(rid, title="../../../../etc/passwd")
    written = result["path"]
    assert str(tmp_path) in written
    assert "etc/passwd" not in written


def test_every_source_shape_normalizes():
    shapes = {
        "score_jd": {"candidates": [{"rank": 1, "username": "octocat", "overall_fit": 82,
                                     "strengths": ["Ships often"], "gaps": []}]},
        "compare": {"candidates": [{"username": "octocat", "name": "Octo Cat", "jd_overall_fit": 74,
                                    "top_languages": ["Go"], "strengths": ["Strong OSS"], "gaps": []}]},
        "bulk": {"rows": [{"rank": 1, "username": "octocat", "name": "Octo Cat", "languages": "Go, Rust",
                           "jd_fit": 66, "key_signal": "Active maintainer", "activity_score": 90}]},
    }
    for source, payload in shapes.items():
        rid = dashboard.register_result(source, payload, {"octocat": _profile()})
        candidates = dashboard.build_dataset(dashboard._cache[rid])
        assert len(candidates) == 1, source
        assert candidates[0]["username"] == "octocat", source
        assert candidates[0]["rank"] == 1, source
        assert candidates[0]["score"] > 0, source


def test_errored_candidates_are_skipped():
    payload = {"candidates": [
        {"rank": 1, "username": "ok", "score": 50, "strengths": [], "gaps": []},
        {"username": "gone", "error": "404"},
    ]}
    rid = dashboard.register_result("rank", payload, {})
    assert dashboard.build(rid)["candidate_count"] == 1


def test_result_with_only_errors_returns_an_error():
    rid = dashboard.register_result("rank", {"candidates": [{"username": "gone", "error": "404"}]}, {})
    assert "error" in dashboard.build(rid)


def test_facets_come_from_real_language_and_topic_data():
    rid = dashboard.register_result("rank", _rank_payload(), {"octocat": _profile()})
    candidates = dashboard.build_dataset(dashboard._cache[rid])
    assert set(dashboard.facets(candidates)) >= {"TypeScript", "Rust", "bundler"}


def test_footer_disclaimer_is_present():
    rid = dashboard.register_result("rank", _rank_payload(), {"octocat": _profile()})
    html = _read(dashboard.build(rid)["path"])
    assert "not ability" in html


def test_offer_is_the_first_key_so_it_is_not_buried(tmp_path):
    from github_talent_mcp.tools._offer import _attach_offer

    payload = _attach_offer(_rank_payload(), "rank", _rank_payload()["candidates"], {})
    assert next(iter(payload)) == "next_action"

    text = json.dumps(payload, indent=2)
    position = text.split("\n").index('  "next_action": {') + 1
    assert position <= 2, f"offer starts at line {position}"


def test_attach_offer_returns_payload_unchanged_when_nothing_scoreable():
    from github_talent_mcp.tools._offer import _attach_offer

    payload = {"candidates": [{"username": "gone", "error": "404"}]}
    assert _attach_offer(payload, "rank", payload["candidates"], {}) is payload


def test_instruction_tells_the_host_to_end_its_reply_with_the_question():
    offer = dashboard.next_action("rank-0001", 3)
    assert "final line" in offer["instruction"]
    assert "even" in offer["instruction"]
