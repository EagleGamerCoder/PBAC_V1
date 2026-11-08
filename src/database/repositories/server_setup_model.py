"""Persistent Server Configuration records."""
from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base

class ServerConfiguration(Base):
    __tablename__ = "server_configurations"

    discord_guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    roblox_group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    verification_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rules_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    information_one_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    information_two_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    information_three_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
