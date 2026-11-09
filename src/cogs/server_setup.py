"""Slash commands for configuring individual Discord servers."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.services.setup_service import SetupError

logger = logging.getLogger(__name__)


class SetupConfigModal(discord.ui.Modal, title="Configure this Discord server"):
    roblox_group_id = discord.ui.TextInput(
        label="Roblox group ID",
        placeholder="Enter the Roblox group ID",
        min_length=1,
        max_length=15,
        required=True,
    )
    verification_channel_id = discord.ui.TextInput(
        label="Verification channel ID",
        placeholder="Enter the verification text-channel ID",
        min_length=1,
        max_length=20,
        required=True,
    )
    rules_channel_id = discord.ui.TextInput(
        label="Rules channel ID",
        placeholder="Enter the rules text-channel ID",
        min_length=1,
        max_length=20,
        required=True,
    )
    information_channel_ids = discord.ui.TextInput(
        label="Information channel IDs (optional)",
        placeholder="Up to 3 IDs, separated by commas; leave blank to skip",
        min_length=0,
        max_length=62,
        required=False,
    )

    def __init__(self, cog: "ServerSetup") -> None:
        super().__init__()
        self.cog = cog

    @staticmethod
    def _parse_id(value: str, label: str) -> int:
        raw = value.strip()
        if not raw.isdigit() or int(raw) <= 0:
            raise SetupError(f"{label} must be a positive number.")
        return int(raw)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send(
                "This command can only be used inside a Discord server.",
                ephemeral=True,
            )
            return

        try:
            group_id = self._parse_id(self.roblox_group_id.value, "Roblox group ID")
            verification_id = self._parse_id(
                self.verification_channel_id.value, "Verification channel ID"
            )
            rules_id = self._parse_id(self.rules_channel_id.value, "Rules channel ID")

            raw_information_ids = self.information_channel_ids.value.strip()
            information_ids: list[int | None] = []
            if raw_information_ids:
                parts = [part.strip() for part in raw_information_ids.split(",")]
                if len(parts) > 3 or any(not part for part in parts):
                    raise SetupError(
                        "Enter up to three information channel IDs separated by commas."
                    )
                information_ids = [
                    self._parse_id(part, "Information channel ID") for part in parts
                ]
            information_ids.extend([None] * (3 - len(information_ids)))

            await self.cog.bot.setup_service.start(
                interaction,
                guild.id,
                group_id,
                verification_id,
                rules_id,
                information_ids[0],
                information_ids[1],
                information_ids[2],
            )

        except SetupError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        except Exception:
            logger.exception("Unexpected setup failure for guild_id=%s", guild.id)
            await interaction.followup.send(
                "An unexpected error occurred while configuring this server. The issue has been logged.",
                ephemeral=True,
            )


class ServerSetup(commands.Cog):
    """Setup configs for individual server handling."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    setup = app_commands.Group(
        name="setup",
        description="Configure this Discord server's Roblox connection and panels.",
    )

    @setup.command(name="configure", description="Configure this server for Roblox verification.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def configure(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(SetupConfigModal(self))

    @setup.command(name="update", description="Repost this server's configured panels.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def update(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a Discord server.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            posted = await self.bot.setup_service.update(interaction, interaction.guild.id)
            await interaction.followup.send(
                "Configured panels posted:\n" + "\n".join(posted),
                ephemeral=True,
            )
        except SetupError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        except Exception:
            logger.exception("Unexpected setup update failure for guild_id=%s", interaction.guild.id)
            await interaction.followup.send(
                "An unexpected error occurred while updating this server's panels. The issue has been logged.",
                ephemeral=True,
            )

    @setup.command(name="update-info", description="Repost this server's configured panels.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def update_info(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a Discord server.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            posted = await self.bot.setup_service.update_info(interaction, interaction.guild.id)
            await interaction.followup.send(
                "Configured panels posted:\n" + "\n".join(posted),
                ephemeral=True,
            )
        except SetupError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        except Exception:
            logger.exception("Unexpected setup update failure for guild_id=%s", interaction.guild.id)
            await interaction.followup.send(
                "An unexpected error occurred while updating this server's panels. The issue has been logged.",
                ephemeral=True,
            )
    

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerSetup(bot))
