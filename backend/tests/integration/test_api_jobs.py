"""
Integration tests for the jobs API.
Uses FastAPI TestClient with a mocked DB session — no real database needed.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import fake_job


class TestHealthEndpoint:
    async def test_health_ok(self, async_client):
        client, _ = async_client
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestCreateJob:
    async def test_creates_job_returns_201(self, async_client):
        client, session = async_client
        job = fake_job(title="Test Job")
        session.get.return_value = None
        session.refresh.side_effect = lambda obj: None

        # Make the job returned after refresh
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        with patch("aios.api.routers.jobs.Job") as MockJob, \
             patch("aios.api.routers.jobs.EventEmitter.emit", new_callable=AsyncMock), \
             patch("aios.workers.scheduler_tasks.dispatch_job") as mock_dispatch:
            mock_dispatch.apply_async = MagicMock()
            mock_instance = fake_job(title="Test Job")
            MockJob.return_value = mock_instance
            session.refresh.side_effect = None

            r = await client.post("/api/v1/jobs", json={
                "title": "Test Job",
                "description": "Integration test job",
                "priority": "NORMAL",
                "input_payload": {},
            })

        assert r.status_code == 201

    async def test_missing_title_returns_422(self, async_client):
        client, _ = async_client
        r = await client.post("/api/v1/jobs", json={"priority": "NORMAL"})
        assert r.status_code == 422

    async def test_invalid_payload_json_returns_422(self, async_client):
        client, _ = async_client
        r = await client.post("/api/v1/jobs", json={
            "title": "x",
            "input_payload": "not-a-dict",
        })
        assert r.status_code == 422


class TestListJobs:
    async def test_list_jobs_returns_200(self, async_client):
        client, session = async_client
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        r = await client.get("/api/v1/jobs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_invalid_status_filter_returns_400(self, async_client):
        client, _ = async_client
        r = await client.get("/api/v1/jobs?status_filter=BOGUS")
        assert r.status_code == 400
        assert "BOGUS" in r.json()["detail"]

    async def test_limit_enforced(self, async_client):
        client, session = async_client
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        # limit=1001 should be clamped / rejected (le=1000)
        r = await client.get("/api/v1/jobs?limit=1001")
        assert r.status_code == 422


class TestGetJob:
    async def test_returns_404_for_missing_job(self, async_client):
        client, session = async_client
        session.get.return_value = None
        r = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")
        assert r.status_code == 404

    async def test_returns_job_when_found(self, async_client):
        client, session = async_client
        job = fake_job(title="Found Job")
        session.get.return_value = job

        with patch("aios.api.routers.jobs.JobResponse.model_validate", return_value={
            "id": str(job.id), "title": "Found Job", "status": "PENDING",
        }):
            r = await client.get(f"/api/v1/jobs/{job.id}")
        assert r.status_code == 200
