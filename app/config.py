from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # MongoDB settings
    MONGO_URI: str
    DATABASE_NAME: str = "ecosmart"
    
    # JWT settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Google OAuth settings
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    
    # Gemini API settings
    GOOGLE_API_KEY: str
    
    # Testing settings
    BYPASS_AUTH: bool = False
    
    # Twilio Settings
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    ADMIN_PHONE_NUMBER: str = ""
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings() 