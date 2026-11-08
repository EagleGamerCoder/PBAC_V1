"""Setup configs for individual server handling."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.ui.embeds import create_pbac_embed

class SetupConfigModal(discord.ui.Modal, title="Setup step 1"):
    roblox_group_id = discord.ui.TextInput(
        label="Roblox group id",
        placeholder="Enter the exact Roblox group id...",
        min_length=3,
        max_length=15,
        required=True,
    )
    verification_channel_id = discord.ui.TextInput(
        label="Verification channel id",
        placeholder="Enter the exact Discord verification channel id...",
        min_length=17,
        max_length=19,
        required=True,
    )
    rules_channel_id = discord.ui.TextInput(
        label="Rules channel id",
        placeholder="Enter the exact Discord rules channel id...",
        min_length=17,
        max_length=19,
        required=True,
    )

    def __init__(self, cog: "ServerSetup") -> None:
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        try: 
            self.cog.setup_service.start(roblox_group_id, verification_channel_id, rules_channel_id)
        except SetupError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        
class ServerSetup(commands.Cog):
    """Setup configs for individual server handling."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.started_at = discord.utils.utcnow()

    @app_commands.command(name="setup", description="Setup a config for a server.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction) -> None:
        """Begin the setup process."""
        await interaction.response.send_modal(SetupConfigModal(self))

async def setup(bot: commands.Bot) -> None:
    """Load this cog as a discord.py extension."""
    await bot.add_cog(ServerSetup(bot))
