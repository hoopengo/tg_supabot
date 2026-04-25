from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_prefix="",
        env_file_encoding="utf-8",
        env_file=".env",
    )

    TOKEN: SecretStr = Field()
    ADMIN_IDS: list[int] = [876980354]
    POSTGRES_USER: str = Field()
    POSTGRES_PASSWORD: str = Field()
    POSTGRES_DB: str = Field()
    POSTGRES_HOST: str = Field()
    POSTGRES_PORT: str = Field()
    REDIS_HOST: str = Field()
    REDIS_PORT: int = Field()
    HF_TOKEN: str = Field()
    LOGFARE_API_KEY: str = Field()
    BASE_TOXICITY_ENCOURAGE: float = 0.8


config = Config()
