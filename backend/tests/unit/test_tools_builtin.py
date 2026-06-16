"""
Unit tests for built-in tool implementations.
All external I/O is mocked — no network calls.
"""
from unittest.mock import MagicMock, patch


class TestWebSearch:
    def test_returns_formatted_results(self):
        fake_results = [
            {"title": "Result A", "href": "https://a.com", "body": "Snippet A"},
            {"title": "Result B", "href": "https://b.com", "body": "Snippet B"},
        ]
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = iter(fake_results)

        with patch("aios.tools.builtin.web_search.DDGS", return_value=mock_ddgs):
            from aios.tools.builtin.web_search import web_search
            result = web_search("test query")

        assert result["query"] == "test query"
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "Result A"
        assert result["results"][0]["url"] == "https://a.com"
        assert result["results"][0]["snippet"] == "Snippet A"

    def test_returns_empty_on_ddgs_error(self):
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.side_effect = RuntimeError("network error")

        with patch("aios.tools.builtin.web_search.DDGS", return_value=mock_ddgs):
            from aios.tools.builtin.web_search import web_search
            result = web_search("failing query")

        assert result["results"] == []
        assert "error" in result

    def test_result_keys_present(self):
        fake = [{"title": "T", "href": "https://x.com", "body": "S"}]
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = iter(fake)

        with patch("aios.tools.builtin.web_search.DDGS", return_value=mock_ddgs):
            from aios.tools.builtin.web_search import web_search
            result = web_search("x")

        r = result["results"][0]
        assert "title" in r and "url" in r and "snippet" in r


class TestReadUrl:
    def _make_mock_response(self, html: str, status: int = 200):
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.status_code = status
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_extracts_visible_text(self):
        html = """<html><head><title>Test Page</title></head>
        <body>
          <script>alert('x')</script>
          <nav>skip me</nav>
          <p>Main content here.</p>
          <p>Second paragraph.</p>
        </body></html>"""

        with patch("httpx.get", return_value=self._make_mock_response(html)):
            from aios.tools.builtin.read_url import read_url
            result = read_url("https://example.com")

        assert result["url"] == "https://example.com"
        assert result["title"] == "Test Page"
        assert "Main content here" in result["content"]
        assert "alert" not in result["content"]
        assert "skip me" not in result["content"]

    def test_respects_4000_char_limit(self):
        big_text = "word " * 2000  # ~10 000 chars
        html = f"<html><head><title>T</title></head><body><p>{big_text}</p></body></html>"

        with patch("httpx.get", return_value=self._make_mock_response(html)):
            from aios.tools.builtin.read_url import read_url
            result = read_url("https://example.com")

        assert len(result["content"]) <= 4_000

    def test_returns_error_on_exception(self):
        with patch("httpx.get", side_effect=Exception("connection refused")):
            from aios.tools.builtin.read_url import read_url
            result = read_url("https://bad.example.com")

        assert result["content"] == ""
        assert "error" in result
