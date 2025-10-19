"""Application configuration management."""

from functools import lru_cache
from typing import Any

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        validate_default=True,
    )

    # Application
    APP_NAME: str = Field(default="DokTalk")
    APP_ENV: str = Field(default="development")
    APP_DEBUG: bool = Field(default=True)
    APP_VERSION: str = Field(default="1.0.0")

    # API
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_WORKERS: int = Field(default=4)

    # Security
    SECRET_KEY: str = Field(default="change-this-secret-key-in-production")
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000"])

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Database
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://doktalk_user:password@localhost:5432/doktalk"
    )
    DB_POOL_SIZE: int = Field(default=20)
    DB_MAX_OVERFLOW: int = Field(default=10)
    DB_POOL_TIMEOUT: int = Field(default=30)
    DB_POOL_RECYCLE: int = Field(default=3600)

    # Redis
    REDIS_URL: RedisDsn = Field(default="redis://:password@localhost:6379/0")
    CACHE_DEFAULT_TTL: int = Field(default=3600)
    CACHE_SESSION_TTL: int = Field(default=86400)

    # ARQ (Async Task Queue)
    ARQ_REDIS_URL: str = Field(default="redis://localhost:6379/0")
    ARQ_MAX_JOBS: int = Field(default=10)
    ARQ_WORKER_NAME: str = Field(default="doktalk-worker")

    # MinIO (S3-compatible Object Storage)
    MINIO_ENDPOINT: str = Field(default="localhost:9000")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin")
    MINIO_SECRET_KEY: str = Field(default="minioadmin")
    MINIO_USE_SSL: bool = Field(default=False)  # Set to True in production
    MINIO_REGION: str = Field(default="ru-central-1")

    # MinIO Buckets
    MINIO_BUCKET_RECORDINGS: str = Field(default="audio-recordings")
    MINIO_BUCKET_MEDIA: str = Field(default="doktalk-media")
    MINIO_BUCKET_EXPORTS: str = Field(default="doktalk-exports")
    MINIO_BUCKET_BACKUPS: str = Field(default="doktalk-backups")

    # Whisper (Speech Recognition)
    WHISPER_MODEL: str = Field(default="base")  # tiny, base, small, medium, large-v3
    WHISPER_DEVICE: str = Field(default="cpu")  # cpu or cuda
    WHISPER_LANGUAGE: str = Field(default="ru")  # Russian by default
    WHISPER_COMPUTE_TYPE: str = Field(default="int8")  # int8, float16, float32

    # Speaker Diarization
    HF_TOKEN: str | None = Field(default=None)  # Hugging Face token for pyannote models
    DIARIZATION_ENABLED: bool = Field(default=True)  # Enable speaker diarization
    DIARIZATION_NUM_SPEAKERS: int = Field(default=2)  # Expected speakers (doctor + patient)

    # Diarization Performance Tuning
    DIARIZATION_SEGMENTATION_BATCH_SIZE: int = Field(
        default=32,
        description="Batch size for segmentation model (higher=faster but more memory)"
    )
    DIARIZATION_EMBEDDING_BATCH_SIZE: int = Field(
        default=32,
        description="Batch size for embedding model (higher=faster but more memory)"
    )

    # Pre-VAD Trimming (Silero) - Reduces diarization input by 20-40%
    DIARIZATION_ENABLE_PRE_VAD: bool = Field(
        default=True,
        description="Enable pre-VAD trimming to remove silence before diarization (20-40% speedup)"
    )
    DIARIZATION_VAD_IMPL: str = Field(
        default="silero",
        description="VAD implementation to use (silero only for now)"
    )
    DIARIZATION_VAD_PAD_MS: int = Field(
        default=180,
        description="Padding in milliseconds to add around speech segments (prevents clipping)"
    )
    DIARIZATION_VAD_MIN_SPEECH_MS: int = Field(
        default=200,
        description="Minimum speech duration in milliseconds (filter out very short sounds)"
    )
    DIARIZATION_VAD_MIN_SILENCE_MS: int = Field(
        default=300,
        description="Minimum silence duration in milliseconds (defines segment boundaries)"
    )
    DIARIZATION_VAD_THRESHOLD: float = Field(
        default=0.5,
        description="Speech probability threshold for VAD (0.0-1.0, higher = more conservative)"
    )
    DIARIZATION_VAD_FRAME_MS: int = Field(
        default=30,
        description="VAD frame size in milliseconds (30ms recommended by Silero)"
    )
    DIARIZATION_STITCH_GAP_MS: int = Field(
        default=300,
        description="Max gap in milliseconds to stitch adjacent same-speaker segments"
    )

    # Segment Merging
    MERGE_SHORT_PAUSES: bool = Field(default=True)  # Merge segments with pauses < threshold
    MERGE_PAUSE_THRESHOLD: float = Field(default=0.8)  # Max pause (seconds) to merge across

    # Vault
    VAULT_ADDR: str = Field(default="http://localhost:8200")
    VAULT_TOKEN: str = Field(default="dev-only-token")
    VAULT_NAMESPACE: str = Field(default="doktalk")
    VAULT_KV_PATH: str = Field(default="secret/data/doktalk")

    # JWT
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # Multi-tenancy
    DEFAULT_TENANT_ID: str = Field(default="00000000-0000-0000-0000-000000000001")

    # Compliance
    DATA_LOCALIZATION_COUNTRY: str = Field(default="RU")
    DATA_RETENTION_YEARS: int = Field(default=7)
    AUDIT_LOG_ENABLED: bool = Field(default=True)

    # OpenTelemetry
    OTEL_ENABLED: bool = Field(default=True)
    OTEL_SERVICE_NAME: str = Field(default="doktalk-api")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(default="http://localhost:4317")

    # Feature flags
    FEATURE_SOAP_GENERATION: bool = Field(default=True)
    FEATURE_ICD10_SUGGESTIONS: bool = Field(default=True)
    FEATURE_ORDER_BLOCKS: bool = Field(default=True)
    FEATURE_PDF_EXPORT: bool = Field(default=True)
    FEATURE_EHR_COPY: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        """Validate settings and apply production defaults."""
        # Ensure production has secure defaults
        if self.APP_ENV == "production":
            if self.SECRET_KEY == "change-this-secret-key-in-production":
                raise ValueError("SECRET_KEY must be changed in production")
            if not self.MINIO_USE_SSL:
                raise ValueError("MINIO_USE_SSL must be True in production")

        # Validate diarization settings
        if self.DIARIZATION_ENABLED and not self.HF_TOKEN:
            raise ValueError("HF_TOKEN required when DIARIZATION_ENABLED=True")

        # Validate whisper device/compute type compatibility
        if self.WHISPER_DEVICE == "cpu" and self.WHISPER_COMPUTE_TYPE not in ["int8", "int16", "float32"]:
            raise ValueError(f"WHISPER_COMPUTE_TYPE={self.WHISPER_COMPUTE_TYPE} not supported on CPU")

        return self

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.APP_ENV == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings (singleton pattern)."""
    return Settings()


# Global settings instance
settings = get_settings()
