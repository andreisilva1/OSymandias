"""
E2E tests — require the full stack to be running.
Run with: docker compose up -d && pytest tests/e2e -v

Marked with @pytest.mark.e2e so they can be skipped in CI without the stack:
    pytest tests/unit tests/integration          # fast, no stack
    pytest tests/e2e -m e2e                      # full stack required
"""
import time
import uuid

import httpx
import pytest

BASE = "http://localhost:8000"
TIMEOUT = 10


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE, timeout=TIMEOUT) as c:
        yield c


def wait_for_status(client, job_id, target_statuses, max_wait=90):
    """Poll job status until it reaches one of the target statuses or times out."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r = client.get(f"/api/v1/jobs/{job_id}")
        r.raise_for_status()
        status = r.json()["status"]
        if status in target_statuses:
            return status
        time.sleep(2)
    raise TimeoutError(f"Job {job_id} did not reach {target_statuses} within {max_wait}s — last status: {status}")


@pytest.mark.e2e
class TestStackHealth:
    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_agents_seeded(self, client):
        r = client.get("/api/v1/agents")
        assert r.status_code == 200
        names = [a["name"] for a in r.json()]
        assert "PlannerAgent" in names
        assert "ResearchAgent" in names

    def test_tools_seeded(self, client):
        r = client.get("/api/v1/tools")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_cors_header_present(self, client):
        r = client.get("/health", headers={"Origin": "http://localhost:3001"})
        assert "access-control-allow-origin" in r.headers


@pytest.mark.e2e
class TestJobCrud:
    def test_create_and_retrieve_job(self, client):
        r = client.post("/api/v1/jobs", json={
            "title": f"e2e-crud-{uuid.uuid4().hex[:6]}",
            "description": "E2E CRUD test — safe to delete",
            "priority": "LOW",
            "input_payload": {},
        })
        assert r.status_code == 201
        job_id = r.json()["id"]

        r2 = client.get(f"/api/v1/jobs/{job_id}")
        assert r2.status_code == 200
        assert r2.json()["id"] == job_id

    def test_job_appears_in_list(self, client):
        title = f"e2e-list-{uuid.uuid4().hex[:6]}"
        r = client.post("/api/v1/jobs", json={
            "title": title, "priority": "LOW", "input_payload": {}
        })
        assert r.status_code == 201
        job_id = r.json()["id"]

        r2 = client.get("/api/v1/jobs?limit=100")
        ids = [j["id"] for j in r2.json()]
        assert job_id in ids

    def test_nonexistent_job_returns_404(self, client):
        r = client.get(f"/api/v1/jobs/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_invalid_status_filter_returns_400(self, client):
        r = client.get("/api/v1/jobs?status_filter=NOPE")
        assert r.status_code == 400

    def test_limit_over_1000_returns_422(self, client):
        r = client.get("/api/v1/jobs?limit=9999")
        assert r.status_code == 422


@pytest.mark.e2e
class TestJobLifecycle:
    def test_job_advances_past_pending(self, client):
        """Verifies the scheduler worker picks up the job."""
        r = client.post("/api/v1/jobs", json={
            "title": "e2e-lifecycle-smoke",
            "description": "Return a JSON object with key 'status' set to 'ok'.",
            "priority": "LOW",
            "input_payload": {},
        })
        assert r.status_code == 201
        job_id = r.json()["id"]

        status = wait_for_status(client, job_id, {"PLANNING", "RUNNING", "COMPLETED", "FAILED"}, max_wait=20)
        assert status != "PENDING", "Scheduler worker did not pick up the job"

    def test_job_tasks_created_after_planning(self, client):
        """Verifies PlannerAgent creates at least one task."""
        r = client.post("/api/v1/jobs", json={
            "title": "e2e-tasks-check",
            "description": "Write a one-sentence summary of the word 'hello'.",
            "priority": "LOW",
            "input_payload": {},
        })
        job_id = r.json()["id"]

        # Wait until planning is done (tasks should exist after PLANNING → RUNNING)
        wait_for_status(client, job_id, {"RUNNING", "COMPLETED", "FAILED"}, max_wait=30)

        r2 = client.get(f"/api/v1/jobs/{job_id}/tasks")
        assert r2.status_code == 200
        assert len(r2.json()) > 0, "PlannerAgent produced no tasks"

    def test_full_job_completes(self, client):
        """
        Full lifecycle: PENDING → PLANNING → RUNNING → COMPLETED.
        Uses a minimal prompt to keep LLM cost and time low.
        Requires a configured LLM provider in .env.
        """
        r = client.post("/api/v1/jobs", json={
            "title": "e2e-full-lifecycle",
            "description": (
                "Reply with a single JSON object: "
                '{\"answer\": \"hello world\"}. '
                "Do not do any research. Return the JSON immediately."
            ),
            "priority": "LOW",
            "input_payload": {},
        })
        assert r.status_code == 201
        job_id = r.json()["id"]

        final_status = wait_for_status(
            client, job_id, {"COMPLETED", "FAILED"}, max_wait=90
        )
        assert final_status == "COMPLETED", (
            f"Job ended with status {final_status}. "
            "Check worker logs: docker compose logs worker-agents --tail=50"
        )

        # Verify output was written
        r2 = client.get(f"/api/v1/jobs/{job_id}/output")
        assert r2.status_code == 200
        assert r2.json()["output"] is not None
