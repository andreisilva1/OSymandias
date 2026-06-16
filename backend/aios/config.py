from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # database — credentials must come from .env (docker-compose sets POSTGRES_URL)
    postgres_url: str = "postgresql+asyncpg://aios:aios@postgres:5432/aios"

    # cache + pub/sub
    redis_url: str = "redis://redis:6379/0"

    # celery broker
    rabbitmq_url: str = "amqp://aios:aios@rabbitmq:5672/"

    # vector store
    qdrant_url: str = "http://qdrant:6333"

    # tracing
    otel_exporter_otlp_endpoint: str = "http://jaeger:4317"
    otel_service_name: str = "osymandias"

    # CORS — comma-separated list of allowed origins
    cors_origins: list[str] = ["http://localhost:3001", "http://localhost:3000"]

    # LLM
    llm_default_provider: str = "ollama"
    llm_default_model: str = "llama3.2"
    ollama_base_url: str = "http://host.docker.internal:11434"
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


settings = Settings()
