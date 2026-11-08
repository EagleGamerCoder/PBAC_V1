"""Ticket system."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.ui.embeds import create_pbac_embed

class Ticket(commands.Cog):
    """Ticket system."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.started_at = discord.utils.utcnow()

async def setup(bot: commands.Bot) -> None:
    """Load this cog as a discord.py extension."""
    await bot.add_cog(Ticket(bot))