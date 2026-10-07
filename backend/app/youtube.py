from __future__ import annotations

import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


YOUTUBE_SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_RESULTS_URL = "https://www.youtube.com/results"
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
logger = logging.getLogger(__name__)


def _google_reasons(error: HTTPError) -> str:
    """What Google says about a rejected request (e.g. keyInvalid, API_KEY_HTTP_REFERRER_BLOCKED).
    Only these codes are logged: never the request URL, which carries the key."""
    try:
        detail = json.loads(error.read().decode("utf-8")).get("error", {})
    except (ValueError, OSError, AttributeError):
        return "sin detalle"
    reasons = [item.get("reason") for item in detail.get("errors", []) + detail.get("details", [])
               if isinstance(item, dict) and item.get("reason")]
    return ", ".join(dict.fromkeys(str(reason)[:80] for reason in reasons)) or "sin detalle"


def search_videos(query: str, api_key: str | None = None) -> dict:
    normalized_query = " ".join(query.split())[:200]
    search_url = YOUTUBE_RESULTS_URL + "?" + urlencode({"search_query": normalized_query})
    fallback = {
        "query": normalized_query,
        "mode": "link",
        "search_url": search_url,
        "videos": [],
        # Why there is only a link: no_key, rejected (by Google) or unavailable (out of reach).
        "reason": "no_key",
    }
    if not api_key:
        return fallback

    api_url = YOUTUBE_SEARCH_ENDPOINT + "?" + urlencode(
        {
            "part": "snippet",
            "type": "video",
            "maxResults": 5,
            "q": normalized_query,
            "key": api_key,
        }
    )
    request = Request(api_url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        logger.warning("YouTube rechazó la búsqueda: HTTP %s, motivo: %s", error.code, _google_reasons(error))
        return {**fallback, "reason": "rejected"}
    except (URLError, TimeoutError, ValueError) as error:
        logger.warning("No se pudo contactar con YouTube: %s", type(error).__name__)
        return {**fallback, "reason": "unavailable"}

    videos = []
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId", "")
        snippet = item.get("snippet", {})
        if not VIDEO_ID_PATTERN.fullmatch(video_id):
            continue
        videos.append(
            {
                "video_id": video_id,
                "title": str(snippet.get("title", ""))[:300],
                "channel": str(snippet.get("channelTitle", ""))[:200],
                "thumbnail": "https://i.ytimg.com/vi/{}/mqdefault.jpg".format(video_id),
            }
        )

    return {
        **fallback,
        "mode": "api",
        "reason": None,
        "videos": videos,
    }