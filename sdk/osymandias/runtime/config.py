from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # database
    postgres_url: str = "postgresql+asyncpg://osy:osy@localhost:5432/osymandias"

    # cache + pub/sub
    redis_url: str = "redis://localhost:6379/0"

    # celery broker
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    # vector store
    qdrant_url: str = "http://localhost:6333"

    # tracing (optional — disabled by default when no endpoint is set)
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "osymandias"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # LLM
    llm_default_provider: str = "openai"
    llm_default_model: str = "gpt-4o"
    ollama_base_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # application
    log_level: str = "INFO"
    agent_default_max_iterations: int = 20
    agent_default_timeout_seconds: int = 120
    heartbeat_timeout_seconds: int = 60
    metrics_cache_ttl_seconds: int = 300

    # tool server (internal — set by osy serve)
    tool_server_url: str = "http://localhost:8001"


settings = Settings()
