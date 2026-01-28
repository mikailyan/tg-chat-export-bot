import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    bot_token: str
    max_files: int = 10
    inline_limit: int = 50
    max_file_size: int = 20 * 1024 * 1024

def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Put it in .env or environment variables.")
    return Settings(bot_token=token)
