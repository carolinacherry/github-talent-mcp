from __future__ import annotations

from github_talent_mcp import dashboard


def _attach_offer(
    payload: dict,
    source: str,
    entries: list[dict],
    profiles: dict,
    cache_payload: dict | None = None,
) -> dict:
    """Cache the result and, unless disabled, prepend the dashboard offer.

    The offer goes FIRST: appended to a long candidate payload it lands ~96% of the
    way down, and hosts routinely skim past it after a long tool chain.
    """
    scoreable = [e for e in entries if isinstance(e, dict) and not e.get("error")]
    if not scoreable:
        return payload
    result_id = dashboard.register_result(source, cache_payload or payload, profiles)
    offer = dashboard.next_action(result_id, len(scoreable))
    if not offer:
        return payload
    return {"next_action": offer, **payload}
