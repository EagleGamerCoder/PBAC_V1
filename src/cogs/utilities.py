"""Basic slash commands used to verify that the bot foundation is running."""

from __future__ import annotations

from datetime import datetime, timezone
from platform import python_version

import discord
from discord import app_commands
from discord.ext import commands

from src.ui.embeds import create_pbac_embed
from src.core import __version__
from src.utils.constants import APP_NAME

def format_uptime(started_at: datetime | None) -> str:
    """Format the bot's uptime as a readable duration."""

    if started_at is None:
        return "Unavailable"

    now = discord.utils.utcnow()

    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    total_seconds = max(0, int((now - started_at).total_seconds()))

    days, remainder = divmod(total_seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, _ = divmod(remainder, 60)

    if days:
        return f"{days}d {hours}h {minutes}m"

    if hours:
        return f"{hours}h {minutes}m"

    return f"{minutes}m"

class Utilities(commands.Cog):
    """General, non-sensitive commands available to PBA server members."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.started_at = discord.utils.utcnow()

    @app_commands.command(name="ping", description="Check whether the PBAC is responding.")
    async def ping(self, interaction: discord.Interaction, show_globally: bool) -> None:
        """Report approximate Discord gateway latency."""

        latency_ms = round(self.bot.latency * 1000)

        embed, files = create_pbac_embed(
            title="PBAC Systems Status",
            description=(
                "Pong!"
            ),
        )
        embed.add_field(
            name="System Status",
            value="🟢 Operational",
            inline=True,
        )
        embed.add_field(
            name="Gateway Latency",
            value=f"`{latency_ms} ms`",
            inline=True,
        )
        embed.add_field(
            name="Connection",
            value="Discord Gateway",
            inline=True,
        )
        await interaction.response.send_message(
            embed=embed,
            files=files,
            ephemeral=(not show_globally),
        )

    @app_commands.command(name="botinfo", description="Display basic information about the PBAC.")
    @app_commands.describe(show_globally="Make the response visible to everyone in the channel.")
    async def botinfo(self, interaction: discord.Interaction, show_globally: bool = False) -> None:
        """Display SFD Command statistics and runtime information."""
        bot = self.bot
        guilds = bot.guilds

        # // Application commands.
        command_map = {command.name: command for command in bot.tree.get_commands()}
        # Include guild-specific commands without counting same-named global commands twice.
        if interaction.guild is not None:
            for command in bot.tree.get_commands(guild=interaction.guild):
                command_map[command.name] = command
        command_count = len(command_map)

        # // Server stats
        server_count = len(guilds)
        cached_user_count = len(bot.users)
        text_channel_count = sum(
            len(guild.text_channels)
            for guild in guilds
        )
        voice_channel_count = sum(
            len(guild.voice_channels)
            for guild in guilds
        )
        category_count = sum(
            len(guild.categories)
            for guild in guilds
        )

        # // Connection stats
        latency_ms = round(bot.latency * 1000)
        connection_status = ("Online" if bot.is_ready() else "Connecting")
        shard_count = bot.shard_count
        shard_text = (
            f"{shard_count} configured"
            if shard_count is not None
            else "1 (unsharded)"
        )

        # // Runtime stats
        started_at = self.started_at
        print(started_at)
        uptime = format_uptime(started_at)
        print(uptime)
        extension_count = len(bot.extensions)

        # // Build the embed
        embed, files = create_pbac_embed(
            title="PBA Command | Bot Information",
            description=(
                "Runtime diagnostics and deployment statistics\nfor the Polvito's British Army Command Discord bot.\n\n"
                f"**Current Status:** {'🟢' if bot.is_ready() else '🟡'} "
                f"{connection_status}"
            )
        )
        embed.add_field(
            name="APPLICATION",
            value=(
                f"**Version**\n`{__version__}`\n"
                f"**Discord.py**\n`{discord.__version__}`\n"
                f"**Python**\n`{python_version()}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="CONNECTION",
            value=(
                f"**Gateway Latency**\n`{latency_ms} ms`\n"
                f"**Status**\n`{connection_status}`\n"
                f"**Sharding**\n`{shard_text}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="SERVER COVERAGE",
            value=(
                f"**Connected Servers**\n`{server_count}`\n"
                f"**Cached Users**\n`{cached_user_count}`\n"
                f"**Loaded Extensions**\n`{extension_count}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="CHANNEL STATISTICS",
            value=(
                f"**Text Channels**\n`{text_channel_count}`\n"
                f"**Voice Channels**\n`{voice_channel_count}`\n"
                f"**Categories**\n`{category_count}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="RUNTIME",
            value=(
                f"**Uptime**\n`{uptime}`\n"
                f"**Application**\n`SFD Command`\n"
                f"**Gateway**\n`Discord`"
            ),
            inline=True,
        )
        embed.add_field(
            name="COMMANDS",
            value=(
                f"**Top-Level Commands**\n`{command_count}`\n"
                f"**Command Interface**\n`Slash Commands`\n"
                f"**Application**\n`Operational`"
            ),
            inline=True,
        )

        # // Send the embed
        await interaction.response.send_message(
            embed=embed,
            files=files,
            ephemeral=(not show_globally),
        )

    @app_commands.command(name="serverinfo", description="Display basic information about this server.")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction, show_globally: bool) -> None:
        """Show basic information about the current Discord guild."""

        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a Discord server.",
                ephemeral=True,
            )
            return

        embed, files = create_pbac_embed(
            title=guild.name,
            description=(
                "Discord server information."
            )
        )
        embed.add_field(
            name="Server ID",
            value=f"`{guild.id}`",
            inline=True,
        )
        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(
                guild.created_at,
                style="D",
            ),
            inline=True,
        )
        total_members = guild.member_count or 0
        bot_count = sum(1 for member in guild.members if member.bot)
        human_count = total_members - bot_count
        embed.add_field(
            name="Member Count",
            value=f"Total: `{total_members}`\nBots: `{bot_count}`\nHuman Members: `{human_count}`",
            inline=False,
        )

        if guild.icon is not None:
            embed.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=embed, files=files, ephemeral=(not show_globally))

    @app_commands.command(name="msg", description="Type a msg with the bot.")
    @app_commands.describe(message="The message to send.", title="Optional title for the message.")
    @app_commands.guild_only()
    async def msg(self, interaction: discord.Interaction, message: str, title: str | None) -> None:
        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, discord.abc.Messageable):
            await interaction.followup.send("This channel does not support sending messages.", ephemeral=True)
            return
        
        user_id = interaction.user.id
        if user_id != 1434931977571668113:
            embed, files = create_pbac_embed(title="Nice Try", description=f"Yeah you're not eagle buddy, you could never outmatch his aura {interaction.user.mention}.")
            await channel.send(embed=embed, files=files)
            return
        
        embed, files = create_pbac_embed(title=title or "", description=message)
        await channel.send(embed=embed, files=files)
        await interaction.followup.send("Sent.", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    """Load this cog as a discord.py extension."""
    await bot.add_cog(Utilities(bot))
