import os

class Settings:
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./widget_platform.db")
    
    # Rate Limiting: max requests per window per IP
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    
    # Payload limits (64 KB)
    MAX_PAYLOAD_SIZE_BYTES: int = int(os.getenv("MAX_PAYLOAD_SIZE_BYTES", "65536"))
    
    # Notification settings
    ENABLE_EMAIL_NOTIFICATION: bool = os.getenv("ENABLE_EMAIL_NOTIFICATION", "true").lower() == "true"
    NOTIFICATION_EMAIL_RECIPIENT: str = os.getenv("NOTIFICATION_EMAIL_RECIPIENT", "admin@example.com")

settings = Settings()
