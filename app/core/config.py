from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded in from env vars"""
    model_config = SettingsConfigDict(case_sensitive=False, env_file='.env',extra="ignore")

    database_url: str

    google_client_id: str = ""
    google_client_secret: str = ""
    openai_api_key: str = ""

    app_name: str = "Email Agent API"
    debug: bool = False
    demo_mode: bool = False

settings = Settings() # type: ignore[call-arg]