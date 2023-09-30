from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    TOKEN: SecretStr = Field()
    ADMIN_IDS: list[int] = [876980354]
    POSTGRES_USER: str = Field()
    POSTGRES_PASSWORD: str = Field()
    POSTGRES_DB: str = Field()
    POSTGRES_HOST: str = Field()
    POSTGRES_PORT: str = Field()
    REDIS_HOST: str = Field()
    REDIS_PORT: int = Field()

    class Config:
        case_sensitive = False
        env_prefix = ""
        env_file_encoding = "utf-8"
        env_file = ".env"


config = Config()
