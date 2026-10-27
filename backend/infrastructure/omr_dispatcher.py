"""Starts the PDF reader in its private GitHub repository (scoremaster-omr; author's decision, 2026-10-27): a
repository_dispatch event "read-pdf" carrying the job. OMR_GITHUB_REPO names the repository and OMR_GITHUB_TOKEN is a
fine-grained token of that repository only (Contents: write, which repository_dispatch requires); it is never logged."""
import os
from typing import Optional

import httpx

API = "https://api.github.com"
TIMEOUT_SECONDS = 20


class GitHubDispatcher:
    def __init__(self, repository: str, token: str, client: Optional[httpx.Client] = None):
        self.repository, self.token = repository, token
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)

    def dispatch(self, payload: dict) -> None:
        response = self.client.post(f"{API}/repos/{self.repository}/dispatches",
                                    headers={"Accept": "application/vnd.github+json",
                                             "Authorization": "Bearer " + self.token,
                                             "X-GitHub-Api-Version": "2022-11-28"},
                                    json={"event_type": "read-pdf", "client_payload": payload})
        if response.status_code != 204:
            raise RuntimeError(f"GitHub answered {response.status_code}")


def configured_dispatcher() -> Optional[GitHubDispatcher]:
    repository, token = os.environ.get("OMR_GITHUB_REPO", "").strip(), os.environ.get("OMR_GITHUB_TOKEN", "").strip()
    return GitHubDispatcher(repository, token) if repository and token else None
