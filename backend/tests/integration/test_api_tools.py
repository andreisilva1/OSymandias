"""
Integration tests for the tools API.
Verifies webhook validation is enforced at the HTTP layer.
"""
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import fake_tool


class TestListTools:
    async def test_returns_200(self, async_client):
        client, session = async_client
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [fake_tool()]
        session.execute.return_value = result_mock

        r = await client.get("/api/v1/tools")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestCreateTool:
    async def test_valid_tool_no_webhook(self, async_client):
        client, session = async_client
        session.get.return_value = None  # no existing tool
        tool = fake_tool(name="my_tool")
        session.refresh.side_effect = None

        with patch("aios.api.routers.tools.ToolDefinition") as MockTool:
            MockTool.return_value = tool
            r = await client.post("/api/v1/tools", json={
                "name": "my_tool",
                "description": "does something",
            })
        assert r.status_code == 201

    async def test_private_ip_webhook_rejected(self, async_client):
        client, _ = async_client
        r = await client.post("/api/v1/tools", json={
            "name": "evil",
            "description": "ssrf attempt",
            "webhook_url": "http://192.168.1.1/internal",
        })
        assert r.status_code == 422

    async def test_localhost_webhook_rejected(self, async_client):
        client, _ = async_client
        r = await client.post("/api/v1/tools", json={
            "name": "evil2",
            "description": "ssrf attempt",
            "webhook_url": "http://localhost/hook",
        })
        assert r.status_code == 422

    async def test_ftp_webhook_rejected(self, async_client):
        client, _ = async_client
        r = await client.post("/api/v1/tools", json={
            "name": "evil3",
            "description": "bad scheme",
            "webhook_url": "ftp://example.com/hook",
        })
        assert r.status_code == 422

    async def test_duplicate_tool_returns_409(self, async_client):
        client, session = async_client
        session.get.return_value = fake_tool(name="existing")

        r = await client.post("/api/v1/tools", json={
            "name": "existing",
            "description": "already exists",
        })
        assert r.status_code == 409
