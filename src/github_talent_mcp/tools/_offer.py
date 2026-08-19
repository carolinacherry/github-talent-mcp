from __future__ import annotations

from github_talent_mcp import dashboard


def _attach_offer(
    payload: dict,
    source: str,
    entries: list[dict],
    profiles: dict,
    cache_payload: dict | None = None,
) -> None:
    """Cache the result and, unless disabled, append the dashboard offer."""
    scoreable = [e for e in entries if isinstance(e, dict) and not e.get("error")]
    if not scoreable:
        return
    result_id = dashboard.register_result(source, cache_payload or payload, profiles)
    offer = dashboard.next_action(result_id, len(scoreable))
    if offer:
        payload["next_action"] = offer
