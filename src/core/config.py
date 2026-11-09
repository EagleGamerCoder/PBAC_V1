"""Loads and configures the .env variables."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.utils.exceptions import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER = "enter-value-here"
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
ENV_PATH = PROJECT_ROOT / ".env"

def parse_bool(name: str, value: str | None, *, default: bool) -> bool:
    # // Parse a conventional environment-variable boolean or raise a clear error
    if value is None or not value.strip():
        return default

    normalised = value.strip().lower()
    if normalised in {"1", "true", "yes", "on"}:
        return True
    if normalised in {"0", "false", "no", "off"}:
        return False

    raise ConfigurationError(f"{name} must be one of true/false, yes/no, on/off, or 1/0; received an invalid value.")

def parse_id(name: str, value: str | None) -> int:
    # // Parse a Discord ID as a positive integer
    if value is None or not value.strip():
        return 0

    raw_value = value.strip()
    if not re.fullmatch(r"[0-9]+", raw_value):
        raise ConfigurationError(f"{name} must contain digits only.")

    parsed = int(raw_value)
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be a positive integer.")
    return parsed

def parse_bounded_int(name: str, value: str | None, *, default: int, minimum: int, maximum: int) -> int:
    # // Parse an integer environment setting and enforce a safe range
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a whole number.") from exc
    if not minimum <= parsed <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}.")
    return parsed

@dataclass(frozen=True, slots=True)
class Settings:
    # // Remains in memory - Never use in logs

    discord_bot_token : str
    guild_id : int 
    sync_global_commands : bool
    log_level : str
    database_url : str
    verification_expiry_minutes: int
    verification_max_attempts: int
    rank_sync_interval_minutes: int
    nickname_format: str
    bod_field_marshal_user_id: int
    bod_second_in_command_user_id: int
    bot_developer_discord_id: int
    log_directory: Path
    project_root: Path

def load_config() -> Settings:
    if not ENV_PATH.is_file():
        raise ConfigurationError(f"Environment file not found: {ENV_PATH}")
    load_dotenv(dotenv_path=ENV_PATH, override=True)

    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token or token.lower() == PLACEHOLDER:
        raise ConfigurationError("DISCORD_BOT_TOKEN is missing or still contains a placeholder.")
    guild_id = parse_id("GUILD_ID", os.getenv("GUILD_ID"))
    if guild_id <= 0:
        raise ConfigurationError("GUILD_ID is missing or still contains a placeholder.")
    sync_global_commands = parse_bool("SYNC_GLOBAL_COMMANDS", os.getenv("SYNC_GLOBAL_COMMANDS"), default=False)
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    if log_level not in VALID_LOG_LEVELS:
        allowed = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ConfigurationError(f"LOG_LEVEL must be one of: {allowed}.")
    
    raw_database_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_database_url:
        default_database_path = (PROJECT_ROOT / "data" / "src.db").as_posix()
        raw_database_url = f"sqlite+aiosqlite:///{default_database_path}"
    if not raw_database_url.startswith(("sqlite+aiosqlite://", "postgresql+asyncpg://")):
        raise ConfigurationError("DATABASE_URL must use sqlite+aiosqlite:// for local development or postgresql+asyncpg:// for PostgreSQL deployments.")
    if raw_database_url.startswith("sqlite+aiosqlite:///"):
        database_path = Path(raw_database_url.replace("sqlite+aiosqlite:///", "", 1))
        if not database_path.is_absolute():
            database_path = PROJECT_ROOT / database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        raw_database_url = (f"sqlite+aiosqlite:///{database_path.as_posix()}")

    verification_expiry_minutes = parse_bounded_int("VERIFICATION_EXPIRY_MINUTES", os.getenv("VERIFICATION_EXPIRY_MINUTES"), default=10, minimum=2, maximum=30)
    verification_max_attempts = parse_bounded_int("VERIFICATION_MAX_ATTEMPTS", os.getenv("VERIFICATION_MAX_ATTEMPTS"), default=5, minimum=1, maximum=10)
    rank_sync_interval_minutes = parse_bounded_int("RANK_SYNC_INTERVAL_MINUTES", os.getenv("RANK_SYNC_INTERVAL_MINUTES"), default=0, minimum=0, maximum=1440)
    nickname_format = os.getenv("NICKNAME_FORMAT", "[{rank_abbr}] {username}").strip() or "[{rank_abbr}] {username}"
    bod_field_marshal_user_id = parse_id("BOD_FIELD_MARSHAL_USER_ID", os.getenv("BOD_FIELD_MARSHAL_USER_ID"))
    bod_second_in_command_user_id = parse_id("BOD_SECOND_IN_COMMAND_USER_ID", os.getenv("BOD_SECOND_IN_COMMAND_USER_ID"))
    bot_developer_discord_id = parse_id("BOT_DEVELOPER_DISCORD_ID", os.getenv("BOT_DEVELOPER_DISCORD_ID"))
    if bod_field_marshal_user_id and bod_field_marshal_user_id == bod_second_in_command_user_id:
        raise ConfigurationError("BOD_FIELD_MARSHAL_USER_ID and BOD_SECOND_IN_COMMAND_USER_ID must be different Roblox user IDs.")
    if not all(token in nickname_format for token in ("{username}",)):
        raise ConfigurationError("NICKNAME_FORMAT must contain the {username} placeholder.")
    if not any(token in nickname_format for token in ("{rank}", "{rank_abbr}")):
        raise ConfigurationError("NICKNAME_FORMAT must contain {rank} or {rank_abbr}.")
    raw_log_directory = os.getenv("LOG_DIRECTORY", "logs").strip() or "logs"
    log_directory = Path(raw_log_directory).expanduser()
    if not log_directory.is_absolute():
        log_directory = PROJECT_ROOT / log_directory
    
    return Settings(
        discord_bot_token=token,
        guild_id=guild_id,
        sync_global_commands=sync_global_commands,
        log_level=log_level,
        database_url=raw_database_url,
        verification_expiry_minutes=verification_expiry_minutes,
        verification_max_attempts=verification_max_attempts,
        rank_sync_interval_minutes=rank_sync_interval_minutes,
        nickname_format=nickname_format,
        bod_field_marshal_user_id=bod_field_marshal_user_id,
        bod_second_in_command_user_id=bod_second_in_command_user_id,
        bot_developer_discord_id=bot_developer_discord_id,
        log_directory=log_directory,
        project_root=PROJECT_ROOT,
    )
