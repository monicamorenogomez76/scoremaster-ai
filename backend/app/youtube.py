from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


YOUTUBE_SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_RESULTS_URL = "https://www.youtube.com/results"
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def search_videos(query: str, api_key: str | None = None) -> dict:
    normalized_query = " ".join(query.split())[:200]
    search_url = YOUTUBE_RESULTS_URL + "?" + urlencode({"search_query": normalized_query})
    fallback = {
        "query": normalized_query,
        "mode": "link",
        "search_url": search_url,
        "videos": [],
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
    except (HTTPError, URLError, TimeoutError, ValueError):
        return fallback

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
        "videos": videos,
    }