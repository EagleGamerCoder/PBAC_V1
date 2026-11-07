"""Small asynchronous client for Roblox's public endpoints."""
from __future__ import annotations

import httpx


class RobloxAPIError(RuntimeError):
    pass


class RobloxService:
    BASE_USERS = "https://users.roblox.com"
    BASE_GROUPS = "https://groups.roblox.com"

    def __init__(self, group_id: int) -> None:
        self.group_id = group_id
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(12.0),
            headers={"User-Agent": "PBAC-Verification/1.0"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _get_json(self, url: str, *, params: dict | None = None) -> dict:
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RobloxAPIError("Roblox could not be reached. Please try again shortly.") from exc
        if not isinstance(data, dict):
            raise RobloxAPIError("Roblox returned an unexpected response.")
        return data

    async def find_user(self, username: str) -> dict:
        data = await self._get_json(
            f"{self.BASE_USERS}/v1/users/search",
            params={"keyword": username, "limit": 10},
        )
        matches = [
            item for item in data.get("data", [])
            if str(item.get("name", "")).casefold() == username.casefold()
        ]
        if not matches:
            raise RobloxAPIError("I couldn't find an exact Roblox username match. Check the spelling and try again.")
        if len(matches) > 1:
            raise RobloxAPIError("Roblox returned multiple matching accounts. Please try again later.")
        user_id = int(matches[0]["id"])
        profile = await self.get_user(user_id)
        return profile

    async def get_user(self, user_id: int) -> dict:
        return await self._get_json(f"{self.BASE_USERS}/v1/users/{user_id}")

    async def get_group_rank(self, user_id: int) -> tuple[int, str]:
        data = await self._get_json(
            f"{self.BASE_GROUPS}/v2/users/{user_id}/groups/roles"
        )
        for membership in data.get("data", []):
            group = membership.get("group", {})
            if int(group.get("id", 0)) == self.group_id:
                role = membership.get("role", {})
                return int(role.get("rank", 0)), str(role.get("name", "Guest"))
        return 0, "Guest"

    async def get_profile_description(self, user_id: int) -> str:
        profile = await self.get_user(user_id)
        return str(profile.get("description") or "")
