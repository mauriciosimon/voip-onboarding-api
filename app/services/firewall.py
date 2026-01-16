import asyncssh
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.trusted_ip import TrustedIP

settings = get_settings()

# IP expiration time in hours
IP_EXPIRATION_HOURS = 2


class FirewallError(Exception):
    """Custom exception for Firewall/SSH errors"""
    pass


class FirewallService:
    """Service to manage FreePBX firewall via SSH"""

    def __init__(self, host: Optional[str] = None, user: Optional[str] = None, key_path: Optional[str] = None):
        # Use provided values or fall back to settings (for backwards compatibility)
        self.host = (host or settings.freepbx_host or "").replace("https://", "").replace("http://", "")
        self.user = user or settings.ssh_user
        self.key_path = key_path or settings.ssh_key_path

    @classmethod
    def from_ssh_account(cls, account) -> 'FirewallService':
        """Create FirewallService from an SSHAccount model instance"""
        return cls(
            host=account.host,
            user=account.ssh_user,
            key_path=account.ssh_key_path
        )

    async def _run_command(self, command: str) -> str:
        """Execute command via SSH"""
        try:
            async with asyncssh.connect(
                self.host,
                username=self.user,
                client_keys=[self.key_path],
                known_hosts=None
            ) as conn:
                result = await conn.run(command, check=True)
                return result.stdout
        except asyncssh.Error as e:
            raise FirewallError(f"SSH error: {str(e)}")
        except Exception as e:
            raise FirewallError(f"Connection error: {str(e)}")

    async def trust_ip(self, ip: str, db: Session, user_id: int = None) -> bool:
        """Add IP to trusted zone in FreePBX firewall and track in DB"""
        try:
            # Add to FreePBX firewall
            result = await self._run_command(f"fwconsole firewall trust {ip}")
            success = "Success" in result

            if success:
                # Track in database with expiration
                self._save_trusted_ip(db, ip, user_id)

            return success
        except FirewallError:
            raise
        except Exception as e:
            raise FirewallError(f"Failed to trust IP {ip}: {str(e)}")

    def _save_trusted_ip(self, db: Session, ip: str, user_id: int = None):
        """Save or update trusted IP in database"""
        existing = db.query(TrustedIP).filter(TrustedIP.ip_address == ip).first()

        if existing:
            # Extend expiration
            existing.expires_at = TrustedIP.calculate_expiry(IP_EXPIRATION_HOURS)
            existing.user_id = user_id
        else:
            # Create new record
            trusted_ip = TrustedIP(
                ip_address=ip,
                user_id=user_id,
                expires_at=TrustedIP.calculate_expiry(IP_EXPIRATION_HOURS)
            )
            db.add(trusted_ip)

        db.commit()

    async def untrust_ip(self, ip: str, db: Session = None) -> bool:
        """Remove IP from trusted zone"""
        try:
            result = await self._run_command(f"fwconsole firewall untrust {ip}")
            success = "Success" in result

            # Remove from database if db session provided
            if success and db:
                db.query(TrustedIP).filter(TrustedIP.ip_address == ip).delete()
                db.commit()

            return success
        except FirewallError:
            raise
        except Exception as e:
            raise FirewallError(f"Failed to untrust IP {ip}: {str(e)}")

    async def cleanup_expired_ips(self, db: Session) -> List[str]:
        """Remove all expired IPs from firewall and database"""
        removed_ips = []

        # Get expired IPs from database
        expired = db.query(TrustedIP).filter(
            TrustedIP.expires_at < datetime.utcnow()
        ).all()

        for trusted_ip in expired:
            try:
                # Remove from FreePBX firewall
                await self._run_command(f"fwconsole firewall untrust {trusted_ip.ip_address}")
                removed_ips.append(trusted_ip.ip_address)
                print(f"Removed expired IP: {trusted_ip.ip_address}")
            except Exception as e:
                print(f"Failed to remove IP {trusted_ip.ip_address}: {e}")

        # Delete expired records from database
        db.query(TrustedIP).filter(TrustedIP.expires_at < datetime.utcnow()).delete()
        db.commit()

        return removed_ips

    async def list_trusted(self) -> List[str]:
        """List all trusted IPs/hosts"""
        try:
            result = await self._run_command("fwconsole firewall list trusted")
            lines = result.strip().split('\n')
            ips = [line.strip() for line in lines[1:] if line.strip()]
            return ips
        except Exception as e:
            raise FirewallError(f"Failed to list trusted IPs: {str(e)}")

    async def is_ip_trusted(self, ip: str) -> bool:
        """Check if IP is already trusted"""
        try:
            trusted = await self.list_trusted()
            return ip in trusted or f"{ip}/32" in trusted
        except Exception:
            return False


# Default instance (may not have SSH configured - use from_ssh_account for user-specific connections)
firewall_service = FirewallService()
