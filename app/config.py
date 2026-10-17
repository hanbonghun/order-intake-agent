from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# LangSmith 등 라이브러리는 os.environ을 직접 읽으므로 .env를 환경변수로도 올린다 (이미 설정된 값은 유지)
load_dotenv(override=False)


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

    attachments_dir: str = "data/attachments"   # 수신 첨부 저장 위치 (S3 등으로 교체 가능)
    outbound_domain: str = "sinseon-market.example"  # 우리가 보내는 메일의 Message-ID 도메인

    # 실제 메일 연동 (Gmail: IMAP 수신 + SMTP 발신, 앱 비밀번호)
    mail_address: str | None = None
    mail_app_password: str | None = None
    mail_imap_host: str = "imap.gmail.com"
    mail_smtp_host: str = "smtp.gmail.com"
    mail_poll_seconds: int = 30
    mail_send_enabled: bool = False          # 기본은 발신 안 함 (초안만 저장)
    mail_send_allowlist: str = ""            # 쉼표 구분. 여기 있는 주소로만 발신 (테스트 중 오발송 방지)
    mail_trusted_authserv: str = "mx.google.com"  # 이 서버가 붙인 Authentication-Results만 신뢰

    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: str | None = None


settings = Settings()
