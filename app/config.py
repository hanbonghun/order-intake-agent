from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://intake:intake@localhost:5432/intake"

    # LLM: 노드 코드는 제공사를 모른다. 설정만 바꿔 모델 비교 평가를 돌린다
    llm_provider: str = "ollama"
    llm_model: str = "qwen3:8b"          # extract 등 주 작업
    llm_model_small: str = "qwen3:8b"    # classify 등 단순 작업
    ollama_base_url: str = "http://localhost:11434"


settings = Settings()
