"""Discord interface for British Army Roblox verification."""
from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.services.roblox import RobloxAPIError
from src.services.verification import VerificationError
from src.ui.embeds import create_pbac_embed, create_verification_panel

logger = logging.getLogger(__name__)


class RobloxUsernameModal(discord.ui.Modal, title="Link your Roblox account"):
    username = discord.ui.TextInput(
        label="Roblox username",
        placeholder="Enter your exact Roblox username",
        min_length=3,
        max_length=20,
    )

    def __init__(self, cog: "Verification") -> None:
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            code, user_id, canonical_name = await self.cog.verification_service.begin(
                interaction.user.id, str(self.username.value)
            )
        except VerificationError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        embed, files = create_pbac_embed(
            title="Complete Roblox Verification",
            description=(
                f"**Roblox account:** [{canonical_name}](https://www.roblox.com/users/{user_id}/profile)\n"
                f"**Verification code:** `{code}`\n\n"
                "1. Open your Roblox profile.\n"
                "2. Add the code above to your profile description.\n"
                "3. Save your Roblox profile.\n"
                "4. Return here and select **Confirm Verification**.\n\n"
                f"This code expires in **{self.cog.bot.settings.verification_expiry_minutes} minutes**. "
                "Do not share it with anyone."
            ),
        )
        await interaction.followup.send(embed=embed, files=files, view=ConfirmVerificationView(self.cog), ephemeral=True)


class StartVerificationView(discord.ui.View):
    def __init__(self, cog: "Verification") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Verify Account",
        style=discord.ButtonStyle.primary,
        custom_id="pbac:verification:start",
    )
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(RobloxUsernameModal(self.cog))


class ConfirmVerificationView(discord.ui.View):
    def __init__(self, cog: "Verification") -> None:
        super().__init__(timeout=600)
        self.cog = cog

    @discord.ui.button(label="Confirm Verification", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            _roblox_id, username, role_id, rank_name = await self.cog.verification_service.confirm(interaction.user.id)
        except (VerificationError, RobloxAPIError) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.followup.send("This must be completed inside the British Army Discord server.", ephemeral=True)
            return

        success, message = await self.cog.rank_sync.sync_member(interaction.user)
        if not success:
            # The account is linked after ownership proof even if staff have not configured
            # the Discord mapping yet. Explain that rank assignment needs staff configuration.
            await interaction.followup.send(
                f"Your Roblox account **{username}** has been verified and linked.\n"
                f"Detected group rank: **{rank_name}** (`{role_id}`).\n\n"
                f"However, Discord rank synchronisation could not complete: {message}",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"Your Roblox account **{username}** has been verified and linked.\n{message}",
            ephemeral=True,
        )
        logger.info("Verified Discord user_id=%s Roblox user_id=%s rank_id=%s", interaction.user.id, _roblox_id, role_id)


class Verification(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.verification_service = bot.verification_service
        self.rank_sync = bot.rank_sync
        bot.add_view(StartVerificationView(self))

    async def cog_load(self) -> None:
        interval = self.bot.settings.rank_sync_interval_minutes
        if interval > 0:
            self.periodic_rank_sync.change_interval(minutes=interval)
            self.periodic_rank_sync.start()

    async def cog_unload(self) -> None:
        self.periodic_rank_sync.cancel()

    @app_commands.command(name="verification-panel", description="Post the permanent Roblox verification panel.")
    @app_commands.describe(channel="Channel where the verification panel should be posted.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def verification_panel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        embed, files = create_verification_panel()
        await channel.send(embed=embed, files=files, view=StartVerificationView(self))
        await interaction.response.send_message(f"Verification panel posted in {channel.mention}.", ephemeral=True)

    verification = app_commands.Group(name="verification", description="British Army Roblox account verification")

    @verification.command(name="status", description="View your linked Roblox account.")
    async def status(self, interaction: discord.Interaction) -> None:
        account = await self.verification_service.get_link(interaction.user.id)
        if account is None:
            await interaction.response.send_message("You do not have a linked Roblox account.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"**Roblox account:** [{account.roblox_username}](https://www.roblox.com/users/{account.roblox_user_id}/profile)\n"
            f"**Group rank:** {account.roblox_rank_name} (`{account.roblox_rank_id}`)\n"
            f"**Last synchronised:** {discord.utils.format_dt(account.last_synced_at, style='R') if account.last_synced_at else 'Never'}",
            ephemeral=True,
        )

    @verification.command(name="sync", description="Manually synchronise your British Army rank and Discord roles.")
    async def sync(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Use this command in the server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        success, message = await self.rank_sync.sync_member(interaction.user)
        await interaction.followup.send(message, ephemeral=True)

    @verification.command(name="unlink", description="Unlink your Roblox account from Discord.")
    async def unlink(self, interaction: discord.Interaction) -> None:
        removed = await self.verification_service.unlink(interaction.user.id)
        await interaction.response.send_message(
            "Your Roblox account has been unlinked. Contact staff if you also need your Discord rank roles removed."
            if removed else "You do not have a linked Roblox account.",
            ephemeral=True,
        )

    @app_commands.command(name="verification-sync-member", description="Synchronise a member's British Army rank.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def sync_member(self, interaction: discord.Interaction, member: discord.Member) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        success, message = await self.rank_sync.sync_member(member)
        await interaction.followup.send(message, ephemeral=True)

    @tasks.loop(minutes=30)
    async def periodic_rank_sync(self) -> None:
        guild = self.bot.get_guild(self.bot.settings.guild_id)
        if guild is None:
            return
        async with self.bot.database.session() as session:
            from src.database.repositories.verification_repository import VerificationRepository
            accounts = await VerificationRepository(session).list_accounts()
        for account in accounts:
            member = guild.get_member(account.discord_user_id)
            if member is None:
                continue
            try:
                success, message = await self.rank_sync.sync_member(member)
                if not success:
                    logger.warning("Automatic rank sync skipped for member_id=%s: %s", member.id, message)
            except Exception:
                logger.exception("Automatic rank sync failed for member_id=%s", member.id)

    @periodic_rank_sync.before_loop
    async def before_periodic_rank_sync(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Verification(bot))
