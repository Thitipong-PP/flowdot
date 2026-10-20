from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    APP_NAME: str = "SME Finance Copilot AI Subsystem (Demo Web)"
    DEBUG: bool = False
    AI_SERVICE_TOKEN: str = Field(default="", description="Internal bearer token for trusted backend-to-AI requests")
    MAX_UPLOAD_BYTES: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    
    # Local Ollama Settings
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434/v1", description="Ollama OpenAI-compatible URL")
    
    # Dual-Model Allocation:
    # 1. Main Orchestrator Brain: 4B model for high reasoning, planning & ReAct CoT
    OLLAMA_MAIN_MODEL: str = Field(default="qwen3:4b", description="Master Orchestrator brain model")
    
    # 2. Satellite Workers: 1.7B model for fast, lightweight structured extraction & summary
    OLLAMA_WORKER_MODEL: str = Field(default="qwen3:1.7b", description="Satellite workers (OCR extraction, loan rationale)")
    
    # Typhoon OCR API Settings
    TYPHOON_API_KEY: str = Field(default="", description="Typhoon OCR API key loaded from .env")
    TYPHOON_OCR_API_URL: str = Field(default="https://api.opentyphoon.ai/v1")
    
    # Database & Pipeline Parameters
    MONGO_URI: str = Field(default="mongodb://localhost:27017")
    MONGO_DB_NAME: str = Field(default="fintech_copilot")
    RETRIEVAL_MODE: str = Field(default="in_memory", description="Hybrid retrieval mode: 'in_memory' or 'atlas'")
    DEBOUNCE_WAIT_SECONDS: float = Field(default=3.0, description="Window to batch rapid message+photos")
    FAST_PATH_LATENCY_THRESHOLD_MS: float = Field(default=200.0, description="Max latency for static menu links")

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()
