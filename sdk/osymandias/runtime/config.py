from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # infrastructure — prefixed to avoid collisions with user's own services
    osy_postgres_url: str = "postgresql+asyncpg://osy:osy@localhost:47762/osymandias"
    osy_redis_url: str = "redis://localhost:47763/0"
    osy_rabbitmq_url: str = "amqp://guest:guest@localhost:47764/"
    osy_qdrant_url: str = "http://localhost:47766"

    # tracing (optional — disabled by default when no endpoint is set)
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "osymandias"

    # CORS
    osy_cors_origins: str = "http://localhost:47759,http://localhost:47760"

    # LLM — standard env var names so users can reuse existing keys
    llm_default_provider: str = "openai"
    llm_default_model: str = "gpt-4o"
    ollama_base_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # application
    osy_log_level: str = "INFO"
    agent_default_max_iterations: int = 20
    agent_default_timeout_seconds: int = 120
    heartbeat_timeout_seconds: int = 60
    metrics_cache_ttl_seconds: int = 300

    # tool server (internal — set by osy serve)
    osy_tool_server_url: str = "http://localhost:47761"

    # auth — static API key; empty string disables auth entirely
    osy_api_key: str = ""


settings = Settings()
