"""Starting the PDF reader in the author's private GitHub repository (2026-10-27): a repository_dispatch "read-pdf"
with the job, authorised by a fine-grained token of that repository only. GitHub is faked: no network."""
import json

import httpx
import pytest

from backend.infrastructure.omr_dispatcher import GitHubDispatcher, configured_dispatcher


def test_the_job_is_sent_as_a_repository_dispatch():
    sent = []
    client = httpx.Client(transport=httpx.MockTransport(lambda request: sent.append(request) or httpx.Response(204)))
    GitHubDispatcher("ana/scoremaster-omr", "github-token", client).dispatch({"kind": "score"})
    request = sent[0]
    assert request.url == "https://api.github.com/repos/ana/scoremaster-omr/dispatches"
    assert request.headers["authorization"] == "Bearer github-token"
    assert json.loads(request.content) == {"event_type": "read-pdf", "client_payload": {"kind": "score"}}


def test_a_refusal_from_github_is_an_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    with pytest.raises(RuntimeError):
        GitHubDispatcher("ana/scoremaster-omr", "github-token", client).dispatch({})


def test_the_reader_is_offered_only_when_configured(monkeypatch):
    monkeypatch.delenv("OMR_GITHUB_REPO", raising=False)
    monkeypatch.setenv("OMR_GITHUB_TOKEN", "x")
    assert configured_dispatcher() is None
    monkeypatch.setenv("OMR_GITHUB_REPO", "ana/scoremaster-omr")
    assert configured_dispatcher().repository == "ana/scoremaster-omr"
