"""The reader tells ScoreMaster it started (2026-10-28), before installing PyTorch and copista, so the director sees
«Preparando el lector» instead of waiting without news. Standard library only: it runs before any package is
installed. The job comes from GitHub's event file and its token is masked in the log. A failure to tell never stops
the reading."""
import json
import os
import sys
import urllib.request
from pathlib import Path


def _post(url: str, body: dict, token: str) -> None:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    urllib.request.urlopen(request, timeout=20).close()


def main(post=_post) -> int:
    job = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())["client_payload"]
    print("::add-mask::" + job["token"], flush=True)
    try:
        post(job["callback"].rstrip("/") + "/progress", {"pages_done": 0, "pages_total": 0, "stage": "preparing"},
             job["token"])
    except Exception as error:
        print(f"No se pudo avisar a ScoreMaster del arranque: {type(error).__name__}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
