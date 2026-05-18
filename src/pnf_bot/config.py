"""Configuration loading for the PnF bot.

The bot is configured via a TOML file (default: config.toml in the project root).
Credentials are NEVER committed — config.toml is gitignored.

This module:
- Defines Pydantic models for every config section
- Loads and validates the TOML file
- Surfaces a single `Config` object for the rest of the codebase to consume
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, EmailStr, Field


class DataConfig(BaseModel):
    """Database and universe parameters."""

    db_path: Path
    min_price: float = Field(default=1.00, ge=0)
    backfill_years: int = Field(default=10, ge=1, le=50)


class NorgateConfig(BaseModel):
    """Norgate Data Updater integration parameters.

    The Norgate SDK reads from a local data store maintained by the Norgate
    Data Updater desktop application. There is no separate API key.
    See docs/research/norgate-data.md for setup instructions.
    """

    universe_watchlist: str = "US Equities"
    price_adjustment: str = Field(default="TotalReturn", pattern="^(TotalReturn|Capital|None)$")
    benchmark_symbol: str = "RSP"


class ScoringConfig(BaseModel):
    """Candidate counts per report section (locked 2026-05-18: 10 + 10)."""

    section_a_top_n: int = Field(default=10, ge=1, le=100)
    section_b_top_n: int = Field(default=10, ge=1, le=100)


class ReportConfig(BaseModel):
    """Daily report delivery configuration."""

    recipient_email: EmailStr
    subject_line: str = "Daily PnF stock report"
    delivery_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    delivery_timezone: str
    archive_dir: Path


class EmailConfig(BaseModel):
    """SMTP delivery credentials. Loaded from config.toml; never logged."""

    smtp_host: str
    smtp_port: int = Field(ge=1, le=65535)
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_use_tls: bool = True


class SchedulerConfig(BaseModel):
    """When the analysis pipeline runs each day."""

    run_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    run_timezone: str


class LoggingConfig(BaseModel):
    """Logging output configuration."""

    log_dir: Path
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")


class Config(BaseModel):
    """Top-level configuration object."""

    data: DataConfig
    norgate: NorgateConfig
    scoring: ScoringConfig
    report: ReportConfig
    email: EmailConfig
    scheduler: SchedulerConfig
    logging: LoggingConfig


def load_config(path: Path | str = "config.toml") -> Config:
    """Load and validate the bot's configuration from a TOML file.

    Raises FileNotFoundError if the path does not exist. Raises pydantic
    ValidationError if the file structure does not match the expected schema.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found at {config_path.resolve()}. "
            "Copy config.toml.example to config.toml and fill in the values."
        )

    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    return Config.model_validate(raw)
