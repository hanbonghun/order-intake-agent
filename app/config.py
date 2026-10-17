from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_parse_none_str="")  # 빈 값은 None

    database_url: str = "postgresql://intake:intake@localhost:5432/intake"

    # LLM: 노드 코드는 제공사를 모른다. 설정만 바꿔 모델 비교 평가를 돌린다
    llm_provider: str = "ollama"         # ollama / openai
    llm_model: str = "qwen3:8b"          # extract 등 주 작업
    llm_model_small: str = "qwen3:8b"    # classify 등 단순 작업
    llm_temperature: float | None = 0    # None이면 제공사 기본값 (일부 추론 모델은 temperature 변경 미지원)
    # 비용 계산용 단가 (USD / 100만 토큰). 제공사 가격표 값을 넣는다. 미설정이면 비용 미집계
    llm_price_input_per_mtok: float | None = None
    llm_price_output_per_mtok: float | None = None
    llm_small_price_input_per_mtok: float | None = None
    llm_small_price_output_per_mtok: float | None = None

    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: str | None = None


settings = Settings()
