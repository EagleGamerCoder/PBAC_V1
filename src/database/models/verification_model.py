"""Persistent Roblox verification records."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base


class VerificationChallenge(Base):
    __tablename__ = "verification_challenges"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    roblox_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    roblox_username: Mapped[str] = mapped_column(String(20), nullable=False)
    challenge_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class VerifiedAccount(Base):
    __tablename__ = "verified_accounts"
    __table_args__ = (
        UniqueConstraint("discord_user_id", name="uq_verified_discord"),
        UniqueConstraint("roblox_user_id", name="uq_verified_roblox"),
    )

    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    roblox_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    roblox_username: Mapped[str] = mapped_column(String(20), nullable=False)
    roblox_rank_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    roblox_rank_name: Mapped[str] = mapped_column(String(100), nullable=False, default="Guest")
    verified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
