"""Database operations for Roblox verification."""
from datetime import datetime
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models.verification_model import VerificationChallenge, VerifiedAccount


class VerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_challenge(self, discord_user_id: int) -> VerificationChallenge | None:
        return await self.session.get(VerificationChallenge, discord_user_id)

    async def put_challenge(self, challenge: VerificationChallenge) -> None:
        await self.session.merge(challenge)

    async def delete_challenge(self, discord_user_id: int) -> None:
        await self.session.execute(delete(VerificationChallenge).where(
            VerificationChallenge.discord_user_id == discord_user_id
        ))

    async def get_by_discord_id(self, discord_user_id: int) -> VerifiedAccount | None:
        return await self.session.get(VerifiedAccount, discord_user_id)

    async def get_by_roblox_id(self, roblox_user_id: int) -> VerifiedAccount | None:
        result = await self.session.execute(select(VerifiedAccount).where(
            VerifiedAccount.roblox_user_id == roblox_user_id
        ))
        return result.scalar_one_or_none()

    async def save_account(self, account: VerifiedAccount) -> None:
        await self.session.merge(account)

    async def delete_account(self, discord_user_id: int) -> None:
        await self.session.execute(delete(VerifiedAccount).where(
            VerifiedAccount.discord_user_id == discord_user_id
        ))

    async def list_accounts(self) -> list[VerifiedAccount]:
        result = await self.session.execute(select(VerifiedAccount))
        return list(result.scalars().all())
