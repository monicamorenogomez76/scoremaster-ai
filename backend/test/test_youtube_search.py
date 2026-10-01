import json

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.youtube import search_videos


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


client = TestClient(app)


def test_youtube_search_without_api_key_returns_search_link():
    result = search_videos("Persis Overture James L. Hosay", api_key=None)

    assert result["mode"] == "link"
    assert result["videos"] == []
    assert result["search_url"].startswith("https://www.youtube.com/results?")
    assert "Persis" in result["search_url"]


def test_youtube_search_maps_api_video_results(monkeypatch):
    payload = {
        "items": [
            {
                "id": {"videoId": "abcdefghijk"},
                "snippet": {
                    "title": "Persis Overture",
                    "channelTitle": "Wind Band",
                    "thumbnails": {"medium": {"url": "https://img.example/thumb.jpg"}},
                },
            }
        ]
    }
    monkeypatch.setattr(
        "backend.app.youtube.urlopen",
        lambda _request, timeout: _Response(payload),
    )

    result = search_videos("Persis Overture", api_key="server-only-key")

    assert result["mode"] == "api"
    assert result["videos"] == [
        {
            "video_id": "abcdefghijk",
            "title": "Persis Overture",
            "channel": "Wind Band",
            "thumbnail": "https://i.ytimg.com/vi/abcdefghijk/mqdefault.jpg",
        }
    ]
    assert result["videos"][0]["video_id"] not in result


def test_youtube_search_endpoint_uses_any_score_title_without_api_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

    response = client.get(
        "/youtube/search",
        params={"query": "A work uploaded by the user"},
    )

    assert response.status_code == 200
    assert response.json()["query"] == "A work uploaded by the user"
    assert response.json()["mode"] == "link"