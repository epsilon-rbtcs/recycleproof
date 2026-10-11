import os
from dataclasses import dataclass

@dataclass
class Settings:
    app_env: str = os.getenv("APP_ENV", "development").lower()
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./recycleproof.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_expiry_minutes: int = int(os.getenv("JWT_EXPIRY_MINUTES", "720"))
    demo_session_ttl_minutes: int = int(os.getenv("DEMO_SESSION_TTL_MINUTES", "120"))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    dev_otp_enabled: bool = os.getenv("DEV_OTP_ENABLED", "false").lower() == "true"
    storage_provider: str = os.getenv("STORAGE_PROVIDER", "local").lower()
    aws_region: str = os.getenv("AWS_REGION", "")
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    upload_dir: str = os.getenv("LOCAL_UPLOAD_DIR", "./uploads")
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024

    @property
    def smtp_ready(self):
        return all([self.smtp_host, self.smtp_username, self.smtp_password, self.smtp_from_email])

    @property
    def s3_ready(self):
        return self.storage_provider == "s3" and bool(self.s3_bucket and self.aws_region)

settings = Settings()
