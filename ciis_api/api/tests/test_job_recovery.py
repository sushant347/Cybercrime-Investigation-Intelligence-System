"""Recovery from a process that died mid-processing.

Jobs run on an in-process thread pool, so anything still queued or running
when the API starts has no worker and never will. Left alone those rows sit
in the dashboard as permanently "running" - which is worse than a visible
failure, because an investigator cannot tell a busy engine from a dead one.
"""
from __future__ import annotations

from api.store import jobs


def test_orphaned_jobs_are_failed_with_an_actionable_message():
    running = jobs.start("evidence_processing", case_id="C1", detail="scan.pdf")
    queued = jobs.start("evidence_processing", case_id="C1", detail="chat.jpg")
    jobs.update(running["id"], status="running")
    jobs.stage(running["id"], "extract", "Extracting text", "OCR page 2 of 9")

    closed = jobs.reconcile_orphaned()
    assert closed == 2

    for job_id in (running["id"], queued["id"]):
        row = jobs.get(job_id)
        assert row["status"] == "failed"
        assert row["finished_at"]
        assert "interrupted" in row["error"].lower()
        assert "again" in row["error"].lower(), "must tell the user what to do"


def test_the_interrupted_step_is_closed_off_with_its_duration():
    job = jobs.start("evidence_processing", case_id="C1", detail="scan.pdf")
    jobs.update(job["id"], status="running")
    jobs.stage(job["id"], "acquire", "Acquiring file")
    jobs.stage(job["id"], "extract", "Extracting text")

    jobs.reconcile_orphaned()

    stages = jobs.get(job["id"])["stages"]
    assert len(stages) == 2
    assert all(s["finished_at"] for s in stages), "no step may be left open"
    assert all(s["duration_ms"] is not None for s in stages)


def test_finished_jobs_are_left_alone():
    done = jobs.start("evidence_processing", case_id="C1", detail="ok.jpg")
    jobs.finish(done["id"], "completed", detail="Processed as EVID_00001")
    failed = jobs.start("evidence_processing", case_id="C1", detail="bad.jpg")
    jobs.finish(failed["id"], "failed", error="Unsupported file type")

    assert jobs.reconcile_orphaned() == 0
    assert jobs.get(done["id"])["status"] == "completed"
    assert jobs.get(done["id"])["detail"] == "Processed as EVID_00001"
    assert jobs.get(failed["id"])["error"] == "Unsupported file type"


def test_reconciling_twice_is_a_no_op():
    jobs.start("evidence_processing", case_id="C1", detail="scan.pdf")
    assert jobs.reconcile_orphaned() == 1
    assert jobs.reconcile_orphaned() == 0


def test_a_recovered_job_reports_as_failed_through_the_api(api):
    job = jobs.start("evidence_processing", case_id="C1", detail="scan.pdf")
    jobs.update(job["id"], status="running")
    jobs.reconcile_orphaned()

    payload = api.get(f"/api/jobs/{job['id']}/").json()
    assert payload["status"] == "failed"
    assert payload["stage"] == ""       # no phantom live step
    assert payload["error"]
