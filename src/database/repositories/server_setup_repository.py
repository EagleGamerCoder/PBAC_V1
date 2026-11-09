"""Database operations for Server setups and configs."""
from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models.server_setup_model import ServerConfiguration

class ServerSetupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def put_configuration(self, configuration: ServerConfiguration) -> ServerConfiguration:
        return await self.session.merge(configuration)
    
    async def get_configuration(self, discord_guild_id: int) -> ServerConfiguration | None:
        return await self.session.get(ServerConfiguration, discord_guild_id)

    async def delete_configuration(self, discord_guild_id: int) -> None:
        await self.session.execute(delete(ServerConfiguration).where(ServerConfiguration.discord_guild_id == discord_guild_id))
