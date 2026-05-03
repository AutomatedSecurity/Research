from __future__ import annotations

from pathlib import Path


APP_DIR_NAME = "riskrank"


def config_dir() -> Path:
    return Path.home() / ".config" / APP_DIR_NAME


def default_credentials_file() -> Path:
    return config_dir() / "credentials.json"


def default_env_file() -> Path:
    return Path.cwd() / ".env"


def default_prompt_file() -> Path:
    return Path(__file__).resolve().parent / "PROMPT.md"
