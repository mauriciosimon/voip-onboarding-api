import httpx
import secrets
import string
from typing import Optional
from app.config import get_settings

settings = get_settings()


class FreePBXError(Exception):
    """Custom exception for FreePBX API errors"""
    pass


class FreePBXService:
    """Service to interact with FreePBX REST API"""

    def __init__(self):
        self.base_url = f"{settings.freepbx_host}/admin/api/api/rest.php/rest"
        self.headers = {
            "Content-Type": "application/json",
        }
        # FreePBX REST API uses basic auth (user + password)
        self.auth = (settings.freepbx_api_user, settings.freepbx_api_password)

    @staticmethod
    def generate_sip_password(length: int = 16) -> str:
        """Generate a secure random password for SIP extension"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    async def create_extension(
        self,
        extension: str,
        name: str,
        password: Optional[str] = None
    ) -> dict:
        """
        Create a new SIP extension in FreePBX

        Args:
            extension: Extension number (e.g., "1001")
            name: Display name for the extension
            password: SIP password (auto-generated if not provided)

        Returns:
            dict with extension details including password
        """
        if password is None:
            password = self.generate_sip_password()

        # FreePBX REST API payload for creating extension
        payload = {
            "extension": extension,
            "name": name,
            "secret": password,
            "tech": "pjsip",  # Using PJSIP (modern)
            "dial": f"PJSIP/{extension}",
            "devicetype": "fixed",
            "description": f"Auto-created for {name}",
            # Voicemail settings
            "vm": "yes",
            "vmpwd": extension,  # Initial voicemail PIN = extension
        }

        async with httpx.AsyncClient() as client:
            try:
                # FreePBX REST API - Create extension
                response = await client.post(
                    f"{self.base_url}/core/extensions",
                    json=payload,
                    auth=self.auth,
                    headers=self.headers,
                    timeout=30.0
                )

                if response.status_code == 200:
                    # Apply config after creating extension
                    await self._reload_config(client)

                    return {
                        "extension": extension,
                        "password": password,
                        "name": name,
                        "success": True
                    }
                elif response.status_code == 409:
                    raise FreePBXError(f"Extension {extension} already exists")
                else:
                    raise FreePBXError(
                        f"Failed to create extension: {response.status_code} - {response.text}"
                    )

            except httpx.RequestError as e:
                raise FreePBXError(f"Connection error to FreePBX: {str(e)}")

    async def _reload_config(self, client: httpx.AsyncClient) -> None:
        """Apply configuration changes in FreePBX"""
        try:
            await client.post(
                f"{self.base_url}/core/reload",
                auth=self.auth,
                headers=self.headers,
                timeout=60.0
            )
        except httpx.RequestError:
            # Log but don't fail - reload might take time
            pass

    async def delete_extension(self, extension: str) -> bool:
        """Delete an extension from FreePBX"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/core/extensions/{extension}",
                    auth=self.auth,
                    headers=self.headers,
                    timeout=30.0
                )

                if response.status_code == 200:
                    await self._reload_config(client)
                    return True
                return False

            except httpx.RequestError:
                return False

    async def check_extension_exists(self, extension: str) -> bool:
        """Check if an extension already exists"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/core/extensions/{extension}",
                    auth=self.auth,
                    headers=self.headers,
                    timeout=10.0
                )
                return response.status_code == 200
            except httpx.RequestError:
                return False


# Singleton instance
freepbx_service = FreePBXService()
