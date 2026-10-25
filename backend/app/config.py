"""Central configuration. Everything comes from environment variables (.env for local dev)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- security ---
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
    cors_origins: list = field(
        default_factory=lambda: [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
    )
    cors_origin_regex: str = os.getenv("CORS_ORIGIN_REGEX", "")  # e.g. https://.*\.vercel\.app

    # --- demo users (seeded at startup; passwords come from env, never from code) ---
    demo_student_id: str = os.getenv("DEMO_STUDENT_ID", "student1")
    demo_student_name: str = os.getenv("DEMO_STUDENT_NAME", "Demo Student")
    demo_student_password: str = os.getenv("DEMO_STUDENT_PASSWORD", "")
    demo_faculty_id: str = os.getenv("DEMO_FACULTY_ID", "faculty1")
    demo_faculty_name: str = os.getenv("DEMO_FACULTY_NAME", "Demo Faculty")
    demo_faculty_password: str = os.getenv("DEMO_FACULTY_PASSWORD", "")

    # --- extra accounts re-created at every start (needed on hosts with a temporary disk, e.g. Render free) ---
    # Format:  id|name|role|password ; id|name|role|password   (name may be empty)
    extra_users: str = os.getenv("EXTRA_USERS", "")

    # --- self sign-up: a private access code per role (empty = sign-up closed for that role) ---
    student_signup_code: str = os.getenv("STUDENT_SIGNUP_CODE", "")
    faculty_signup_code: str = os.getenv("FACULTY_SIGNUP_CODE", "")

    # --- storage ---
    db_path: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "portal.db"))
    index_dir: Path = Path(os.getenv("INDEX_DIR", str(BASE_DIR / "data" / "index")))
    handbook_dir: Path = Path(os.getenv("HANDBOOK_DIR", str(BASE_DIR / "data" / "handbooks")))

    # --- retrieval ---
    embed_model: str = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    retrieval_mode: str = os.getenv("RETRIEVAL_MODE", "hybrid")  # hybrid | bm25
    top_k: int = int(os.getenv("TOP_K", "5"))
    dense_min_score: float = float(os.getenv("DENSE_MIN_SCORE", "0.62"))
    min_coverage: float = float(os.getenv("MIN_COVERAGE", "0.55"))

    # --- LLM (any OpenAI-compatible chat-completions API) ---
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    llm_model: str = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    llm_fallback_model: str = os.getenv("LLM_FALLBACK_MODEL", "openai/gpt-oss-20b")
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "40"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1500"))  # reasoning models spend part of this on thinking
    llm_reasoning_effort: str = os.getenv("LLM_REASONING_EFFORT", "")  # "low" for gpt-oss; leave empty for other models

    # --- abuse protection (protects the free LLM quota) ---
    chat_rate_per_minute: int = int(os.getenv("CHAT_RATE_PER_MINUTE", "10"))
    max_question_chars: int = int(os.getenv("MAX_QUESTION_CHARS", "500"))


settings = Settings()
