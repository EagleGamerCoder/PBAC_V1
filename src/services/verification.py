"""Verification challenge orchestration."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from src.database.models.verification_model import VerificationChallenge, VerifiedAccount
from src.database.repositories.verification_repository import VerificationRepository
from src.services.roblox import RobloxService, RobloxAPIError


class VerificationError(RuntimeError):
    pass


class VerificationService:
    def __init__(self, database, roblox: RobloxService, *, expiry_minutes: int, max_attempts: int) -> None:
        self.database = database
        self.roblox = roblox
        self.expiry_minutes = expiry_minutes
        self.max_attempts = max_attempts

    @staticmethod
    def _hash(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    async def begin(self, discord_user_id: int, username: str) -> tuple[str, int, str]:
        username = username.strip()
        if not username or len(username) > 20:
            raise VerificationError("Enter a valid Roblox username.")
        try:
            profile = await self.roblox.find_user(username)
        except RobloxAPIError as exc:
            raise VerificationError(str(exc)) from exc

        roblox_id = int(profile["id"])
        canonical_name = str(profile["name"])
        code = f"PBAC-{secrets.token_hex(4).upper()}"

        async with self.database.session() as session:
            repo = VerificationRepository(session)
            existing = await repo.get_by_roblox_id(roblox_id)
            if existing and existing.discord_user_id != discord_user_id:
                raise VerificationError("That Roblox account is already linked to another Discord account.")
            challenge = VerificationChallenge(
                discord_user_id=discord_user_id,
                roblox_user_id=roblox_id,
                roblox_username=canonical_name,
                challenge_hash=self._hash(code),
                expires_at=datetime.utcnow() + timedelta(minutes=self.expiry_minutes),
                attempts=0,
            )
            await repo.put_challenge(challenge)
            await session.commit()
        return code, roblox_id, canonical_name

    async def confirm(self, discord_user_id: int) -> tuple[int, str, int, str]:
        async with self.database.session() as session:
            repo = VerificationRepository(session)
            challenge = await repo.get_challenge(discord_user_id)
            if challenge is None:
                raise VerificationError("You don't have an active verification. Start again using the verification panel.")
            if challenge.expires_at < datetime.utcnow():
                await repo.delete_challenge(discord_user_id)
                await session.commit()
                raise VerificationError("Your verification code has expired. Please start again.")
            if challenge.attempts >= self.max_attempts:
                await repo.delete_challenge(discord_user_id)
                await session.commit()
                raise VerificationError("You have reached the verification attempt limit. Start again.")

            description = await self.roblox.get_profile_description(challenge.roblox_user_id)
            # Compare the exact challenge token as a standalone item.
            if challenge.challenge_hash not in {
                self._hash(token.strip()) for token in description.split()
            }:
                challenge.attempts += 1
                await session.commit()
                remaining = max(0, self.max_attempts - challenge.attempts)
                raise VerificationError(f"Code not found in your Roblox profile description. Attempts remaining: {remaining}.")

            # Ownership verification is independent of group membership. Non-members
            # are linked as civilians and receive the configured Civilian role on sync.
            role_id, rank_name, rank_number = await self.roblox.get_group_role(challenge.roblox_user_id)
            linked_elsewhere = await repo.get_by_roblox_id(challenge.roblox_user_id)
            if linked_elsewhere and linked_elsewhere.discord_user_id != discord_user_id:
                raise VerificationError("That Roblox account is already linked to another Discord account.")

            account = VerifiedAccount(
                discord_user_id=discord_user_id,
                roblox_user_id=challenge.roblox_user_id,
                roblox_username=challenge.roblox_username,
                roblox_rank_id=role_id,
                roblox_rank_name=rank_name,
                verified_at=datetime.utcnow(),
                last_synced_at=datetime.utcnow(),
            )
            await repo.save_account(account)
            await repo.delete_challenge(discord_user_id)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise VerificationError("This Roblox account is already linked to another Discord account.") from exc
            return challenge.roblox_user_id, challenge.roblox_username, role_id, rank_name

    async def get_link(self, discord_user_id: int) -> VerifiedAccount | None:
        async with self.database.session() as session:
            return await VerificationRepository(session).get_by_discord_id(discord_user_id)

    async def unlink(self, discord_user_id: int) -> bool:
        async with self.database.session() as session:
            repo = VerificationRepository(session)
            account = await repo.get_by_discord_id(discord_user_id)
            if account is None:
                return False
            await repo.delete_account(discord_user_id)
            await session.commit()
            return True
