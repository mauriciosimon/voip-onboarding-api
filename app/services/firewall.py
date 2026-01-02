import asyncssh
from typing import Optional, List
from app.config import get_settings

settings = get_settings()


class FirewallError(Exception):
    """Custom exception for Firewall/SSH errors"""
    pass


class FirewallService:
    """Service to manage FreePBX firewall via SSH"""

    def __init__(self):
        self.host = settings.freepbx_host.replace("https://", "").replace("http://", "")
        self.user = settings.ssh_user
        self.key_path = settings.ssh_key_path

    async def _run_command(self, command: str) -> str:
        """Execute command via SSH"""
        try:
            async with asyncssh.connect(
                self.host,
                username=self.user,
                client_keys=[self.key_path],
                known_hosts=None  # In production, use proper known_hosts
            ) as conn:
                result = await conn.run(command, check=True)
                return result.stdout
        except asyncssh.Error as e:
            raise FirewallError(f"SSH error: {str(e)}")
        except Exception as e:
            raise FirewallError(f"Connection error: {str(e)}")

    async def trust_ip(self, ip: str) -> bool:
        """Add IP to trusted zone in FreePBX firewall"""
        try:
            result = await self._run_command(f"fwconsole firewall trust {ip}")
            return "Success" in result
        except FirewallError:
            raise
        except Exception as e:
            raise FirewallError(f"Failed to trust IP {ip}: {str(e)}")

    async def untrust_ip(self, ip: str) -> bool:
        """Remove IP from trusted zone"""
        try:
            result = await self._run_command(f"fwconsole firewall untrust {ip}")
            return "Success" in result
        except FirewallError:
            raise
        except Exception as e:
            raise FirewallError(f"Failed to untrust IP {ip}: {str(e)}")

    async def list_trusted(self) -> List[str]:
        """List all trusted IPs/hosts"""
        try:
            result = await self._run_command("fwconsole firewall list trusted")
            lines = result.strip().split('\n')
            # Skip header line and extract IPs
            ips = [line.strip() for line in lines[1:] if line.strip()]
            return ips
        except Exception as e:
            raise FirewallError(f"Failed to list trusted IPs: {str(e)}")

    async def is_ip_trusted(self, ip: str) -> bool:
        """Check if IP is already trusted"""
        try:
            trusted = await self.list_trusted()
            # Check for exact match or CIDR match
            return ip in trusted or f"{ip}/32" in trusted
        except Exception:
            return False


# Singleton instance
firewall_service = FirewallService()
