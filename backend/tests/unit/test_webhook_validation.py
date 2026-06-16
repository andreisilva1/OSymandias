"""
Unit tests for webhook URL validation (SSRF guard in tools router).
"""
import pytest
from pydantic import ValidationError

from aios.api.routers.tools import ToolCreate, _validate_webhook_url


class TestValidateWebhookUrl:
    def test_valid_https(self):
        assert _validate_webhook_url("https://api.example.com/hook") == "https://api.example.com/hook"

    def test_valid_http(self):
        assert _validate_webhook_url("http://api.example.com/hook") == "http://api.example.com/hook"

    def test_none_passes_through(self):
        assert _validate_webhook_url(None) is None

    def test_rejects_localhost(self):
        with pytest.raises(ValueError, match="private"):
            _validate_webhook_url("http://localhost/hook")

    def test_rejects_127(self):
        with pytest.raises(ValueError, match="private"):
            _validate_webhook_url("http://127.0.0.1/hook")

    def test_rejects_10_x(self):
        with pytest.raises(ValueError, match="private"):
            _validate_webhook_url("http://10.0.0.1/hook")

    def test_rejects_192_168(self):
        with pytest.raises(ValueError, match="private"):
            _validate_webhook_url("http://192.168.1.1/hook")

    def test_rejects_172_16(self):
        with pytest.raises(ValueError, match="private"):
            _validate_webhook_url("http://172.16.0.1/hook")

    def test_rejects_non_http_scheme(self):
        with pytest.raises(ValueError, match="http"):
            _validate_webhook_url("ftp://example.com/hook")

    def test_rejects_file_scheme(self):
        with pytest.raises(ValueError, match="http"):
            _validate_webhook_url("file:///etc/passwd")


class TestToolCreateModel:
    def test_valid_tool_no_webhook(self):
        t = ToolCreate(name="my_tool", description="desc")
        assert t.webhook_url is None

    def test_valid_tool_with_webhook(self):
        t = ToolCreate(name="my_tool", description="desc", webhook_url="https://api.example.com/hook")
        assert t.webhook_url == "https://api.example.com/hook"

    def test_tool_rejects_ssrf_webhook(self):
        with pytest.raises(ValidationError):
            ToolCreate(name="evil", description="desc", webhook_url="http://192.168.0.1/internal")
