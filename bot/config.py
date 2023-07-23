from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    TOKEN: str = Field(env="TOKEN")
    ADMIN_IDS: list[int] = [876980354]

    class Config:
        case_sensitive = False
        env_prefix = ""
        env_file_encoding = "utf-8"
        env_file = ".env"


config = Config()
