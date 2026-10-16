"""Read-only GitHub PR #9 comment observation for the four-role pilot.

Transport observation is not authenticated sender identity or recipient delivery.
No comment body is executed or treated as instructions.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable
from urllib.request import Request, urlopen

from .four_role_ledger import FourRoleLedger, CoordinationError

_API = "https://api.github.com/repos/thebrazenbeard/intranel/issues/9/comments"
_FENCE = re.compile(r"\x60\x60\x60json[ \t]*\r?\n(.*?)\r?\n\x60\x60\x60", re.IGNORECASE | re.DOTALL)
_ALLOWED = frozenset({"REQUEST", "ACK", "WAIT", "CONFLICT"})
_MAX_BODY = 256 * 1024
_MAX_PAGE = 2 * 1024 * 1024
_MAX_PROVIDER_PAGE = 100  # hard bound; one invocation still reads <= 3 pages


def _fetch_page(page: int) -> list[dict[str, Any]]:
    if type(page) is not int or not 1 <= page <= _MAX_PROVIDER_PAGE:
        raise CoordinationError("poll page outside bounded range")
    url = f"{_API}?per_page=100&page={page}"
    request = Request(url, headers={
        "User-Agent": "Vera-Intranel-ReadOnly-Pilot/1.0",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=15) as response:
        raw = response.read(_MAX_PAGE + 1)
    if len(raw) > _MAX_PAGE:
        raise CoordinationError("GitHub comment page too large")
    obj = json.loads(raw.decode("utf-8"))
    if type(obj) is not list or len(obj) > 100:
        raise CoordinationError("unexpected GitHub comments response")
    return obj


def observe_pr_comments(
    ledger: FourRoleLedger,
    *,
    pages: int = 1,
    start_page: int = 1,
    fetch_page: Callable[[int], list[dict[str, Any]]] = _fetch_page,
    ingest_packet: Callable[[dict[str, Any], str], dict[str, Any]] | None = None,
) -> dict[str, int | bool | str | None]:
    if type(pages) is not int or not 1 <= pages <= 3:
        raise CoordinationError("poll limited to 1..3 pages")
    if (type(start_page) is not int or not 1 <= start_page <= _MAX_PROVIDER_PAGE
            or start_page + pages - 1 > _MAX_PROVIDER_PAGE):
        raise CoordinationError("poll window outside bounded page range")
    result: dict[str, int | bool | str | None] = {
        "comments_read": 0, "fenced_packets": 0, "observed_new": 0,
        "duplicates": 0, "identity_conflicts": 0,
        "rejected_unqualified": 0, "ignored_noncausal": 0,
        "origin_authenticated": False, "delivered": False, "ack_accepted": False,
        "coverage_complete": False, "coverage_status": "HOLD_NOT_SCANNED",
        "next_page": None,
        "start_page": start_page, "last_page": None, "pages_read": 0,
        "terminal_page_observed": False,
    }
    last_page_full = False
    for index in range(start_page, start_page + pages):
        comments = fetch_page(index)
        result["last_page"] = index
        result["pages_read"] += 1
        if type(comments) is not list or len(comments) > 100:
            raise CoordinationError("invalid provider pagination result")
        for item in comments:
            if type(item) is not dict:
                raise CoordinationError("malformed provider comment")
            comment_id = item.get("id")
            body = item.get("body")
            if type(comment_id) is not int or comment_id < 1 or type(body) is not str:
                raise CoordinationError("missing provider comment identity/body")
            if len(body.encode("utf8")) > _MAX_BODY:
                result["rejected_unqualified"] += 1
                continue
            result["comments_read"] += 1
            for raw in _FENCE.findall(body)[:4]:
                result["fenced_packets"] += 1
                try:
                    packet = json.loads(raw)
                except (ValueError, TypeError):
                    result["rejected_unqualified"] += 1
                    continue
                if type(packet) is not dict:
                    result["rejected_unqualified"] += 1
                    continue
                if packet.get("performative") not in _ALLOWED:
                    result["ignored_noncausal"] += 1
                    continue
                try:
                    observed = (ingest_packet or ledger.observe)(
                        packet,
                        f"github:thebrazenbeard/intranel#9/comment/{comment_id}",
                    )
                except (ValueError, TypeError, KeyError):
                    result["rejected_unqualified"] += 1
                    continue
                label = observed["ingest"]
                if label == "OBSERVED_NEW":
                    result["observed_new"] += 1
                elif label == "DUPLICATE":
                    result["duplicates"] += 1
                elif label == "CONFLICT":
                    result["identity_conflicts"] += 1
                else:
                    raise CoordinationError("unknown observation classification")
        last_page_full = len(comments) == 100
        if not last_page_full:
            break
    result["terminal_page_observed"] = not last_page_full
    # A resumed window proves nothing about preceding pages or provider
    # snapshot continuity; its local terminal page is not global coverage.
    result["coverage_complete"] = start_page == 1 and not last_page_full
    if last_page_full:
        result["coverage_status"] = ("HOLD_COMMENT_PAGE_CEILING"
                                     if index == _MAX_PROVIDER_PAGE
                                     else "HOLD_COMMENT_PAGINATION_LIMIT")
        result["next_page"] = index + 1 if index < _MAX_PROVIDER_PAGE else None
    elif start_page != 1:
        result["coverage_status"] = "HOLD_PRECEDING_PAGES_UNVERIFIED"
    else:
        result["coverage_status"] = "COMPLETE_SCANNED_WINDOW"
    return result
