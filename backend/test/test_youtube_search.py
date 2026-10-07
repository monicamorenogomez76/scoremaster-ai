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

# 2026-10-07: on Render the search "did not work" and nothing said why; every failure fell back to a
# plain link in silence. The reason is now logged (never the key) and told to the musician.
def test_without_a_key_the_reason_is_that_the_search_is_not_configured():
    assert search_videos("Persis Overture", api_key=None)["reason"] == "no_key"


def test_a_key_rejected_by_google_is_logged_with_its_reason_but_never_the_key(monkeypatch, caplog):
    import io
    from urllib.error import HTTPError
    body = json.dumps({"error": {"code": 403, "errors": [{"reason": "forbidden"}],
                                 "details": [{"reason": "API_KEY_HTTP_REFERRER_BLOCKED"}]}}).encode()

    def reject(request, timeout):
        raise HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(body))
    monkeypatch.setattr("backend.app.youtube.urlopen", reject)

    result = search_videos("Persis Overture", api_key="secret-server-key")

    assert result["mode"] == "link" and result["reason"] == "rejected"
    assert "HTTP 403" in caplog.text and "API_KEY_HTTP_REFERRER_BLOCKED" in caplog.text
    assert "secret-server-key" not in caplog.text


def test_youtube_out_of_reach_is_reported_as_unavailable(monkeypatch, caplog):
    from urllib.error import URLError

    def unreachable(request, timeout):
        raise URLError("timed out")
    monkeypatch.setattr("backend.app.youtube.urlopen", unreachable)
    assert search_videos("Persis Overture", api_key="secret-server-key")["reason"] == "unavailable"
    assert "secret-server-key" not in caplog.text


def test_a_working_search_has_no_reason(monkeypatch):
    monkeypatch.setattr("backend.app.youtube.urlopen", lambda _request, timeout: _Response({"items": []}))
    assert search_videos("Persis Overture", api_key="k")["reason"] is None
