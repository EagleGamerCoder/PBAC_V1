"""Setup configs for individual server handling."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.ui.embeds import create_pbac_embed

class SetupConfigModal(discord.ui.Modal, title="Setup step 1"):
    roblox_group_id = discord.ui.TextInput(
        label="Roblox group id",
        placeholder="Enter the exact Roblox group id",
        min_length=3,
        max_length=15,
        required=True,
    )
    verification_channel_id = discord.ui.TextInput(
        label="Verification channel id",
        placeholder="Enter the exact Discord verification channel id",
        min_length=17,
        max_length=19,
        required=True,
    )
    rules_channel_id = discord.ui.TextInput(
        label="Rules channel id",
        placeholder="Enter the exact Discord rules channel id",
        min_length=17,
        max_length=19,
         required=True,
    )
    information_one_channel_id = discord.ui.TextInput(
        label="Information channel id 1,
        placeholder="Enter the exact Discord channel id OR leave blank if you don't wish to have one",
        min_length=17,
        max_length=19,
        required=False,
    )
    information_two_channel_id = discord.ui.TextInput(
        label="Information channel id 2,
        placeholder="Enter the exact Discord channel id OR leave blank if you don't wish to have one",
        min_length=17,
        max_length=19,
        required=False,
    )
    information_three_channel_id = discord.ui.TextInput(
        label="Information channel id 3,
        placeholder="Enter the exact Discord channel id OR leave blank if you don't wish to have one",
        min_length=17,
        max_length=19,
        required=False,
    )

    def __init__(self, cog: "ServerSetup") -> None:
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("This command can only be used inside a server.", ephemeral=True)
            return
    
        try:
            try:
                group_id = int(self.roblox_group_id.value.strip())
                v_chan_id = int(self.verification_channel_id.value.strip())
                r_chan_id = int(self.rules_channel_id.value.strip())
                one_info_chan_id = int(self.information_one_channel_id.value.strip()) or None
                two_info_chan_id = int(self.information_two_channel_id.value.strip()) or None
                three_info_chan_id = int(self.information_three_channel_id.value.strip()) or None
            except ValueError:
                raise SetupError("One or more of the IDs you entered contains invalid characters. Please enter numbers only.")

            verification_channel = guild.get_channel(v_chan_id)
            rules_channel = guild.get_channel(r_chan_id)
            if not verification_channel or not isinstance(verification_channel, discord.TextChannel):
                raise SetupError(f"Could not find a valid text channel with the ID `{v_chan_id}` in this server.")
            if not rules_channel or not isinstance(rules_channel, discord.TextChannel):
                raise SetupError(f"Could not find a valid text channel with the ID `{r_chan_id}` in this server.")
            if one_info_chan_id != None and (not one_info_chan_id or not isinstance(one_info_chan_id, discord.TextChannel)):
                raise SetupError(f"Could not find a valid text channel with the ID `{one_info_chan_id}` in this server.")
            if two_info_chan_id != None and (not two_info_chan_id or not isinstance(two_info_chan_id, discord.TextChannel)):
                raise SetupError(f"Could not find a valid text channel with the ID `{two_info_chan_id}` in this server.")
            if three_info_chan_id != None and (not three_info_chan_id or not isinstance(three_info_chan_id, discord.TextChannel)):
                raise SetupError(f"Could not find a valid text channel with the ID `{three_info_chan_id}` in this server.")

            await self.cog.setup_service.start(interaction, guild.id, group_id, v_chan_id, r_chan_id, one_info_chan_id, two_info_chan_id, three_info_chan_id)
            await interaction.followup.send("Server setup Success.", ephemeral=True)

        except SetupError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        
class ServerSetup(commands.Cog):
    """Setup configs for individual server handling."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.started_at = discord.utils.utcnow()

    setup = app_commands.group(name="setup", description="Organise a server's connection to the bot.")
    
    @setup.command(name="configure", description="Setup a config for a server.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def configure(self, interaction: discord.Interaction) -> None:
        """Begin the setup process."""
        await interaction.response.send_modal(SetupConfigModal(self))
        
    @setup.command(name="update", description="Updates a server's configured components.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def update(self, interaction: discord.Interaction) -> None:
        """Update the setup components."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        try: 
            self.cog.setup_service.update(interaction, interaction.guild.id)
        except SetupError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        

async def setup(bot: commands.Bot) -> None:
    """Load this cog as a discord.py extension."""
    await bot.add_cog(ServerSetup(bot))
