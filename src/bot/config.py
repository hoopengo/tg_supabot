from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    TOKEN: SecretStr = Field(env="TOKEN")
    ADMIN_IDS: list[int] = [876980354]
    POSTGRES_USER: str = Field(env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(env="POSTGRES_PASSWORD")
    POSTGRES_DB: str = Field(env="POSTGRES_DB")
    POSTGRES_HOST: str = Field(env="POSTGRES_HOST")
    POSTGRES_PORT: str = Field(env="POSTGRES_PORT")

    class Config:
        case_sensitive = False
        env_prefix = ""
        env_file_encoding = "utf-8"
        env_file = ".env"


config = Config()
