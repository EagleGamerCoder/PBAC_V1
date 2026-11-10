
"""Independant Bot status monitoring and maintenance management."""

from __future__ import annotations

import asyncio
import json

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from src.core import __version__

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Project root (the folder containing .env)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
STATUS_PATH = PROJECT_ROOT / "data" / "bot_status.json"

load_dotenv(dotenv_path=ENV_PATH, override=True)

DEVELOPER_ID = int(os.getenv("BOT_DEVELOPER_DISCORD_ID", "0"))
STATUS_CHANNEL_ID = int(os.getenv("BOT_STATUS_CHANNEL_ID", "0"))

logger.info("Loading environment from: %s", ENV_PATH)
logger.info("Status channel configured: %s", STATUS_CHANNEL_ID != 0)

DISCONNECT_GRACE_PERIOD = 45


class BotStatus(commands.Cog):
    """Monitors bot connectivity and manages maintenance mode."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        self.maintenance_enabled = False
        self.last_status = "unknown"

        self.disconnect_task: asyncio.Task | None = None
        self.startup_handled = False

        self._load_state()

    def _load_state(self) -> None:
        """Load persistent maintenance state."""

        try:
            if STATUS_PATH.exists():
                with STATUS_PATH.open("r", encoding="utf-8") as file:
                    data = json.load(file)

                self.maintenance_enabled = data.get(
                    "maintenance", False
                )

                self.last_status = data.get(
                    "last_status", "unknown"
                )

        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Could not load bot status state: %s", exc)

    def _save_state(self) -> None:
        """Persist maintenance and connection state."""

        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "maintenance": self.maintenance_enabled,
            "last_status": self.last_status,
        }

        temporary_path = STATUS_PATH.with_suffix(".tmp")

        temporary_path.write_text(
            json.dumps(data, indent=4),
            encoding="utf-8",
        )

        temporary_path.replace(STATUS_PATH)

    async def _send_status(self, title: str, description: str, colour: int) -> bool:
        """Send a status announcement."""

        if STATUS_CHANNEL_ID == 0:
            logger.error("BOT_STATUS_CHANNEL_ID is not configured.")
            return False

        try:
            channel = self.bot.get_channel(STATUS_CHANNEL_ID)

            if channel is None:
                channel = await self.bot.fetch_channel(
                    STATUS_CHANNEL_ID
                )

            embed = discord.Embed(
                title=title,
                description=description,
                colour=colour,
                timestamp=discord.utils.utcnow(),
            )

            embed.set_footer(
                text=f"PBA Command • v{__version__}"
            )

            await channel.send(embed=embed)

            return True

        except (discord.HTTPException, discord.Forbidden) as exc:
            logger.error("Failed to send status message: %s", exc)
            return False

    async def _announce_online(self) -> None:
        """Announce that the bot is operational."""

        if self.maintenance_enabled:
            return

        sent = await self._send_status(
            title="System Operational",
            description=(
                "🟢 **PBAC Command is online.**\n\n"
                "The bot has successfully connected to Discord "
                "and all systems are available."
            ),
            colour=discord.Colour.green(),
        )

        if sent:
            self.last_status = "online"
            self._save_state()

    async def _announce_offline(self) -> None:
        """Announce a sustained Gateway disconnection."""

        if self.maintenance_enabled:
            return

        sent = await self._send_status(
            title="System Offline",
            description=(
                "🔴 **PBAC Command has disconnected.**\n\n"
                "The bot is currently unavailable. "
                "The system will announce when connectivity is restored."
            ),
            colour=discord.Colour.red(),
        )

        if sent:
            self.last_status = "offline"
            self._save_state()

    async def _offline_timer(self) -> None:
        """Wait before announcing a disconnection."""

        try:
            await asyncio.sleep(DISCONNECT_GRACE_PERIOD)

            if self.maintenance_enabled:
                return

            if self.bot.is_ready():
                return

            if self.last_status == "offline":
                return

            await self._announce_offline()

        except asyncio.CancelledError:
            raise

    async def _handle_reconnection(self) -> None:
        """Handle startup and restored connectivity."""

        if self.disconnect_task is not None:
            self.disconnect_task.cancel()
            self.disconnect_task = None

        if self.maintenance_enabled:
            self.startup_handled = True
            return

        if self.last_status == "offline" or not self.startup_handled:
            await self._announce_online()

        self.startup_handled = True

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Handle initial connection and fresh sessions."""

        await self._handle_reconnection()

    @commands.Cog.listener()
    async def on_resumed(self) -> None:
        """Handle successful Gateway session resumption."""

        await self._handle_reconnection()

    @commands.Cog.listener()
    async def on_disconnect(self) -> None:
        """Detect Gateway disconnections."""

        if self.maintenance_enabled:
            return

        if self.disconnect_task is None or self.disconnect_task.done():
            self.disconnect_task = asyncio.create_task(
                self._offline_timer()
            )

    @app_commands.command(
        name="maintenance",
        description="Enable or disable bot maintenance mode.",
    )
    @app_commands.describe(
        action="Whether to enable or disable maintenance mode."
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(
                name="Enable Maintenance",
                value="enable",
            ),
            app_commands.Choice(
                name="Disable Maintenance",
                value="disable",
            ),
        ]
    )
    async def maintenance(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
    ) -> None:

        # Developer permission check
        if (
            DEVELOPER_ID == 0
            or interaction.user.id != DEVELOPER_ID
        ):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        if action.value == "enable":

            if self.maintenance_enabled:
                await interaction.followup.send(
                    "Maintenance mode is already enabled.",
                    ephemeral=True,
                )
                return

            self.maintenance_enabled = True
            self.last_status = "maintenance"

            # Cancel pending offline announcements
            if self.disconnect_task is not None:
                self.disconnect_task.cancel()
                self.disconnect_task = None

            self._save_state()

            sent = await self._send_status(
                title="Maintenance Mode Enabled",
                description=(
                    "🛠️ **PBAC Command is now in maintenance mode.**\n\n"
                    "The bot may temporarily disconnect or restart "
                    "during maintenance.\n\n"
                    "Online and offline notifications are now disabled "
                    "until maintenance mode is ended."
                ),
                colour=discord.Colour.orange(),
            )

            await interaction.followup.send(
                "Maintenance mode enabled. "
                + ("Announcement posted." if sent else
                   "However, the status announcement could not be posted."),
                ephemeral=True,
            )

            await self.bot.change_presence(status=discord.Status.dnd, activity=discord.Game('In Maintenance Mode.'))

        elif action.value == "disable":

            if not self.maintenance_enabled:
                await interaction.followup.send(
                    "Maintenance mode is not currently enabled.",
                    ephemeral=True,
                )
                return

            self.maintenance_enabled = False
            self.last_status = "online"

            self._save_state()

            sent = await self._send_status(
                title="Maintenance Completed",
                description=(
                    "🟢 **PBAC Command maintenance has ended.**\n\n"
                    "The bot is returning to normal operation.\n\n"
                    "Online and offline monitoring has been re-enabled."
                ),
                colour=discord.Colour.green(),
            )

            await interaction.followup.send(
                "Maintenance mode disabled. "
                + ("Announcement posted." if sent else
                   "However, the status announcement could not be posted."),
                ephemeral=True,
            )

            await self.bot.change_presence(status=discord.Status.online, activity=discord.Game(f'Running v{__version__}.'))

    async def announce_shutdown(self) -> None:
        """Announce a planned bot shutdown."""

        if self.maintenance_enabled:
            return

        await self._send_status(
            title="System Offline",
            description=(
                "🔴 **PBAC Command is shutting down.**\n\n"
                "The bot is disconnecting and will be unavailable "
                "until it starts again."
            ),
            colour=discord.Colour.red(),
        )

    async def cog_unload(self) -> None:
        """Cancel background tasks when unloading the cog."""

        if self.disconnect_task is not None:
            self.disconnect_task.cancel()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BotStatus(bot))
