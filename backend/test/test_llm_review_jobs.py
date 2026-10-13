"""The background review stops when the quota is spent (2026-10-13, Render: «La IA ha alcanzado su límite
de uso»): asking the rest only made every passage fail; the next run continues where it stopped."""
from backend.application import llm_review_jobs
from backend.application.ai import ProviderFailure


def run(todo, review):
    saved = []
    llm_review_jobs.PAUSE_SECONDS = 0
    job = llm_review_jobs.start(object(), todo, review, lambda passage, reviewed, features: saved.append(passage))
    llm_review_jobs.wait_for_jobs()
    return job, saved


def test_a_spent_quota_pauses_the_review_instead_of_failing_every_passage():
    asked = []

    def review(passage):
        asked.append(passage)
        if passage >= 2:
            raise ProviderFailure("rate_limit")
        return {}, {}
    job, saved = run([0, 1, 2, 3, 4], review)
    assert saved == [0, 1]
    assert asked == [0, 1, 2, 2], "one wait and retry, then it stops: 3 and 4 are not asked"
    assert (job.state, job.last_error, job.failed) == ("paused", "rate_limit", 0)


def test_other_failures_are_counted_and_the_review_goes_on():
    def review(passage):
        if passage == 1:
            raise ProviderFailure("timeout")
        return {}, {}
    job, saved = run([0, 1, 2], review)
    assert saved == [0, 2] and (job.state, job.failed, job.last_error) == ("done", 1, "timeout")
