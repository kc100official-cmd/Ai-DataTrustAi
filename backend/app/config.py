import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    PROJECT_NAME: str = "DataTrust AI"
    VERSION: str = "1.0.0"
    TAGLINE: str = "Ask your data. Verify every answer."

    HOST: str = os.getenv("DATATRUST_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("DATATRUST_PORT", "8001"))

    DATA_DIR: Path = Path(os.getenv("DATATRUST_DB_DIR", str(BASE_DIR / "backend" / "data"))).resolve()

    # LLM configuration (restricted to <= 8B open-weight models for BIRD benchmark compliance)
    LLM_ENABLED: bool = os.getenv("DATATRUST_LLM_ENABLED", "false").lower() in ("true", "1", "yes")
    LLM_ENDPOINT: str = os.getenv("DATATRUST_LLM_ENDPOINT", "http://localhost:11434/v1")
    LLM_API_KEY: str = os.getenv("DATATRUST_LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("DATATRUST_LLM_MODEL", "llama3.1:8b-instruct-q4_K_M")
    LLM_PARAM_BILLIONS: float = float(os.getenv("DATATRUST_LLM_PARAM_BILLIONS", "8.0"))
    LLM_MAX_ALLOWED_BILLIONS: float = 8.0
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("DATATRUST_LLM_TIMEOUT_SECONDS", "15.0"))

    # Embeddings configuration
    EMBEDDINGS_ENABLED: bool = os.getenv("DATATRUST_EMBEDDINGS_ENABLED", "false").lower() in ("true", "1", "yes")
    EMBEDDING_ENDPOINT: str = os.getenv("DATATRUST_EMBEDDING_ENDPOINT", "http://localhost:11434/v1/embeddings")
    EMBEDDING_MODEL: str = os.getenv("DATATRUST_EMBEDDING_MODEL", "nomic-embed-text")

    # SQL guardrails
    SQL_TIMEOUT_SECONDS: float = float(os.getenv("DATATRUST_SQL_TIMEOUT_SECONDS", "5.0"))
    SQL_MAX_ROWS: int = int(os.getenv("DATATRUST_SQL_MAX_ROWS", "500"))
    SQL_MAX_REPAIR_ATTEMPTS: int = int(os.getenv("DATATRUST_SQL_MAX_REPAIR_ATTEMPTS", "2"))

    # Graph guardrails
    GRAPH_MAX_DEPTH: int = int(os.getenv("DATATRUST_GRAPH_MAX_DEPTH", "5"))
    GRAPH_MAX_NODES: int = int(os.getenv("DATATRUST_GRAPH_MAX_NODES", "150"))

    # BIRD benchmark path
    BIRD_DATASET_PATH: str = os.getenv("DATATRUST_BIRD_DATASET_PATH", "")


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
