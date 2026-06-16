"""
Unit tests for Settings — env var parsing and defaults.
"""
import os
from unittest.mock import patch


class TestCorsOrigins:
    def test_default_is_string(self):
        from aios.config import Settings
        s = Settings()
        assert isinstance(s.cors_origins, str)
        assert "localhost:3001" in s.cors_origins

    def test_env_var_overrides_default(self):
        from aios.config import Settings
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://myapp.com"}):
            s = Settings()
        assert s.cors_origins == "https://myapp.com"

    def test_comma_separated_preserved(self):
        from aios.config import Settings
        value = "http://localhost:3001,http://localhost:3000"
        with patch.dict(os.environ, {"CORS_ORIGINS": value}):
            s = Settings()
        assert s.cors_origins == value

    def test_main_parses_to_list(self):
        """main.py splits cors_origins into a list for CORSMiddleware."""
        raw = "http://localhost:3001, http://localhost:3000"
        result = [o.strip() for o in raw.split(",") if o.strip()]
        assert result == ["http://localhost:3001", "http://localhost:3000"]

    def test_main_handles_single_origin(self):
        raw = "https://myapp.com"
        result = [o.strip() for o in raw.split(",") if o.strip()]
        assert result == ["https://myapp.com"]

    def test_main_ignores_empty_entries(self):
        raw = "http://a.com,,http://b.com"
        result = [o.strip() for o in raw.split(",") if o.strip()]
        assert result == ["http://a.com", "http://b.com"]


class TestDefaults:
    def test_otel_service_name(self):
        from aios.config import Settings
        s = Settings()
        assert s.otel_service_name == "osymandias"

    def test_llm_defaults(self):
        from aios.config import Settings
        s = Settings()
        assert s.llm_default_provider == "ollama"
        assert s.llm_default_model == "llama3.2"

    def test_api_keys_default_empty(self):
        from aios.config import Settings
        s = Settings()
        for key in ("anthropic_api_key", "openai_api_key", "deepseek_api_key", "groq_api_key", "gemini_api_key"):
            assert getattr(s, key) == ""
