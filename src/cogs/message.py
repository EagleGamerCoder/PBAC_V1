"""General bot message commands for bot_developer_discord_id only."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.ui.embeds import create_pbac_embed

class Message(commands.Cog):
    """General bot message commands for bot_developer_discord_id only."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.started_at = discord.utils.utcnow()

    msg = app_commands.Group(name="msg", description="PBA Command Message Commands.")
    
    @msg.command(name="embed", description="Type a embeded msg with the bot. (BOT DEV ONLY)")
    @app_commands.describe(message="The message to send.", title="Optional title for the message.", ping="Wether or not the bot should ping something.", ping_user="The role or user to ping.")
    @app_commands.guild_only()
    async def embed(self, interaction: discord.Interaction, message: str, title: str | None, ping: bool, ping_user: discord.Member | discord.Role | None) -> None:
        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, discord.abc.Messageable):
            await interaction.followup.send("This channel does not support sending messages.", ephemeral=True)
            return
        
        user_id = interaction.user.id
        if user_id != self.bot.settings.bot_developer_discord_id:
            embed, files = create_pbac_embed(title="Sorry, You can't use this command!", description=f"Yeah you're not eagle buddy, you could never outmatch his aura {interaction.user.mention}.")
            await channel.send(embed=embed, files=files)
            return
        
        embed, files = create_pbac_embed(title=title or "", description=message)
        if ping == True and ping_user != None:
            await channel.send(ping_user.mention)
        await channel.send(embed=embed, files=files)
        await interaction.followup.send("Sent.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    """Load this cog as a discord.py extension."""
    await bot.add_cog(Message(bot))
