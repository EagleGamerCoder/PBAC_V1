"""Server setup functionality."""
from __future__ import annotations
from pathlib import Path
import discord
from src.database.models.server_setup_model import ServerConfiguration
from src.database.repositories.server_setup_repository import ServerSetupRepository
from src.services.roblox import RobloxService, RobloxAPIError
from src.services.verification import StartVerificationView, Verification
from src.ui.embeds import create_verification_panel, create_rules_panel, create_pbac_embed
from src.utils.json_loader import load_json_object

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PANEL_PATH = PROJECT_ROOT / "data" / "regiment_info.json"

class SetupError(RuntimeError):
    pass

class SetupService:
    def __init__(self, database) -> None:
        self.database = database

    async def start(
        self, 
        interaction: discord.Interaction, 
        guild_id: int, 
        roblox_group_id: int, 
        verification_channel_id: int, 
        rules_channel_id: int, 
        information_one_channel_id: int | None, 
        information_two_channel_id: int | None, 
        information_three_channel_id: int | None
    ) -> None:
        group_status = RobloxService.check_group()
        if group_status == False:
            raise SetupError("Roblox group id is invalid and does not correspond to a roblox group.")
        
        async with self.database.session() as session:
            repo = ServerSetupRepository(session)
            existing = await repo.get_configuration(guild_id)
            if existing:
                repo.delete_configuration(guild_id)
            
            configuration = ServerConfiguration(
                discord_guild_id = guild_id,
                roblox_group_id = roblox_group_id,
                verification_channel_id = verification_channel_id,
                rules_channel_id = rules_channel_id,
                information_one_channel_id = information_one_channel_id or 0,
                information_two_channel_id = information_two_channel_id or 0,
                information_three_channel_id = information_three_channel_id or 0,
            )
            await repo.put_configuration(self, configuration)
            await session.commit()
            
        await self.update(interaction, guild_id)

    async def update(self, interaction: discord.Interaction, guild_id: int) -> None:
        guild = interaction.guild
        if not guild:
            raise SetupError("Guild could not be found from interaction.")
            
        async with self.database.session() as session:
            repo = ServerSetupRepository(session)
            configuration = await repo.get_configuration(guild_id)
            if configuration is None:
                raise SetupError("This server is not setup. Please ask an administrator to setup the server.")
            
            verification_channel_id = configuration.verification_channel_id
            rules_channel_id = configuration.rules_channel_id
            roblox_group_id = configuration.roblox_group_id
            information_one_channel_id = configuration.information_one_channel_id
            information_two_channel_id = configuration.information_two_channel_id
            information_three_channel_id = configuration.information_three_channel_id
            
            verification_channel = guild.get_channel(verification_channel_id)
            rules_channel = guild.get_channel(rules_channel_id)
            
            if verification_channel:
                await verification_channel.purge(limit=None)
                v_embed, v_files = create_verification_panel()
                await verification_channel.send(embed=v_embed, files=v_files, view=StartVerificationView(Verification))
                await interaction.followup.send(f"Verification panel posted in {verification_channel.mention}.", ephemeral=True)
            
            if rules_channel:
                await rules_channel.purge(limit=None)
                r_embed, r_files = create_rules_panel()
                await rules_channel.send(embed=r_embed, files=r_files)
                await interaction.followup.send(f"Rules panel posted in {rules_channel.mention}.", ephemeral=True)
            
            if information_one_channel_id != 0 and information_one_channel_id is not None and await self._get_embed_info(guild_id, 1) is not None:
                information_one_channel = guild.get_channel(information_one_channel_id)
                if information_one_channel:
                    await information_one_channel.purge(limit=None)
                    one_embed_info = await self._get_embed_info(guild_id, 1)
                    one_embed, one_files = create_pbac_embed(
                        title=one_embed_info.get("title", ""),
                        description=one_embed_info.get("description", ""),
                    )
                    await information_one_channel.send(embed=one_embed, files=one_files)
                    await interaction.followup.send(f"Information panel 1 posted in {information_one_channel.mention}.", ephemeral=True)
            
            if information_two_channel_id != 0 and information_two_channel_id is not None and await self._get_embed_info(guild_id, 2) is not None:
                information_two_channel = guild.get_channel(information_two_channel_id)
                if information_two_channel:
                    await information_two_channel.purge(limit=None)
                    two_embed_info = await self._get_embed_info(guild_id, 2)
                    two_embed, two_files = create_pbac_embed(
                        title=two_embed_info.get("title", ""),
                        description=two_embed_info.get("description", ""),
                    )
                    await information_two_channel.send(embed=two_embed, files=two_files)
                    await interaction.followup.send(f"Information panel 2 posted in {information_two_channel.mention}.", ephemeral=True)
            
            if information_three_channel_id != 0 and information_three_channel_id is not None and await self._get_embed_info(guild_id, 3) is not None:
                information_three_channel = guild.get_channel(information_three_channel_id)
                if information_three_channel:
                    await information_three_channel.purge(limit=None)
                    three_embed_info = await self._get_embed_info(guild_id, 3)
                    three_embed, three_files = create_pbac_embed(
                        title=three_embed_info.get("title", ""),
                        description=three_embed_info.get("description", ""),
                    )
                    await information_three_channel.send(embed=three_embed, files=three_files)
                    await interaction.followup.send(f"Information panel 3 posted in {information_three_channel.mention}.", ephemeral=True)
            
            await session.commit()
            await interaction.followup.send("All panels successfully sent.", ephemeral=True)

    async def _get_embed_info(self, guild_id: int, embed_number: int) -> dict[str, str] | None:
        panel = load_json_object(PANEL_PATH)
        panel_info = panel.get(str(guild_id), "")
        if panel_info == "" or panel_info is None:
            return None
        panel_section = panel_info.get(f"info_{embed_number}", "")
        if panel_section == "" or panel_section is None:
            return None
        return panel_section
