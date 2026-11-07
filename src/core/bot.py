"""Defines the creation of the Discord bot.

Loads cogs and syncs slash commands."""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import discord
from discord.ext import commands

from src.core.config import Settings # Bot configuration settings
from src.utils.constants import APP_NAME
from src.utils.errors import handle_app_command_error
from src.database.connection import Database
from src.database.base import Base
from src.database.models import verification_model as _verification_model  # Register ORM tables.
from src.services.roblox import RobloxService
from src.services.verification import VerificationService
from src.services.rank_sync import RankSyncService

# Add new  cogs here as they are tested and implimented.
INITIAL_EXTENSIONS: tuple[str, ...] = (
    "src.cogs.utilities",
    "src.cogs.verification",
)

"""MAIN BOT CLASS"""
class DiscordBot(commands.Bot):
    def __init__(self, settings : Settings) -> None:
        """Constructs the bot."""
        # // Intents and Permissions
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True

        # // Inital attributes 
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            description=f"{APP_NAME} Discord bot",
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.settings = settings
        self.database = Database(settings.database_url)
        self.roblox = RobloxService(settings.roblox_group_id)
        self.verification_service = VerificationService(
            self.database,
            self.roblox,
            expiry_minutes=settings.verification_expiry_minutes,
            max_attempts=settings.verification_max_attempts,
        )
        self.rank_sync = RankSyncService(
            self.database,
            self.roblox,
            project_root=settings.project_root,
            nickname_format=settings.nickname_format,
            bod_field_marshal_user_id=settings.bod_field_marshal_user_id,
            bod_second_in_command_user_id=settings.bod_second_in_command_user_id,
        )
        self._logged_first_ready = False
        self.tree.on_error = handle_app_command_error

    async def setup_hook(self) -> None:
        """Load extensions and synchronises application commands before gateway events."""
        # Create the initial verification tables. If you later adopt Alembic,
        # move this schema creation into a versioned migration.
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await self.database.check_connection()
        logger.info("Database connectivity verified.")
        logger.info("Loading %d Discord extension(s).", len(INITIAL_EXTENSIONS))

        for extension in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info("Loaded extension: %s", extension)
            except Exception:
                logger.exception("Failed to load extension: %s", extension)
                raise

        await self._sync_application_commands()

    async def _sync_application_commands(self) -> None:
        """Sync commands to the developer guild, or globally when not configured."""
        if self.settings.guild_id is not None:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d application command(s) to development guild %s.", len(synced), self.settings.guild_id)
            return

        if self.settings.sync_global_commands:
            synced = await self.tree.sync()
            logger.info("Synced %d global application command(s).", len(synced))
            return

        logger.warning("Application commands were loaded locally but not synced. Set GUILD_ID for development, or explicitly set SYNC_GLOBAL_COMMANDS=true for global sync.")

    async def on_ready(self) -> None:
        """Log the first successful gateway connection."""
        if not self._logged_first_ready:
            logger.info("Connected to Discord as %s (user_id=%s).", self.user, self.user.id if self.user else "unknown")
            self._logged_first_ready = True
            await self.change_presence(status=discord.Status.online, activity=discord.Game('Currently in development.'))
        else:
            logger.info("Discord gateway session is ready again.")

    async def on_disconnect(self) -> None:
        """Log a gateway disconnect: discord.py will generally attempt to reconnect."""
        logger.warning("Disconnected from the Discord gateway: waiting for reconnection.")

    async def close(self) -> None:
        """Close the Discord client cleanly."""
        logger.info("Shutting down %s bot.", APP_NAME)
        try:
            await super().close()
        finally:
            await self.database.dispose()