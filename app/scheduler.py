import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.database import SessionLocal
from app.services.firewall import FirewallService
from app.models.trusted_ip import TrustedIP
from app.models.user import User
from app.models.ssh_account import SSHAccount

# Scheduler instance
scheduler = AsyncIOScheduler()


async def cleanup_expired_ips_job():
    """Background job to remove expired IPs from firewall across all SSH accounts"""
    print("Running IP cleanup job...")
    db = SessionLocal()
    try:
        # Get expired IPs with their associated users and SSH accounts
        expired = db.query(TrustedIP).filter(
            TrustedIP.expires_at < datetime.utcnow()
        ).all()

        if not expired:
            print("No expired IPs to clean up")
            return

        removed_ips = []
        # Group by user's SSH account and clean up
        for trusted_ip in expired:
            try:
                # Get user's SSH account if available
                if trusted_ip.user_id:
                    user = db.query(User).filter(User.id == trusted_ip.user_id).first()
                    if user and user.ssh_account:
                        fw_service = FirewallService.from_ssh_account(user.ssh_account)
                        await fw_service._run_command(f"fwconsole firewall untrust {trusted_ip.ip_address}")
                        removed_ips.append(trusted_ip.ip_address)
                        print(f"Removed expired IP: {trusted_ip.ip_address}")
            except Exception as e:
                print(f"Failed to remove IP {trusted_ip.ip_address}: {e}")

        # Delete expired records from database
        db.query(TrustedIP).filter(TrustedIP.expires_at < datetime.utcnow()).delete()
        db.commit()

        if removed_ips:
            print(f"Cleaned up {len(removed_ips)} expired IPs: {removed_ips}")
    except Exception as e:
        print(f"Error in cleanup job: {e}")
    finally:
        db.close()


def start_scheduler():
    """Start the background scheduler"""
    # Run cleanup every 10 minutes
    scheduler.add_job(
        cleanup_expired_ips_job,
        trigger=IntervalTrigger(minutes=10),
        id="cleanup_expired_ips",
        name="Cleanup expired IPs from firewall",
        replace_existing=True
    )
    scheduler.start()
    print("IP cleanup scheduler started (runs every 10 minutes)")


def stop_scheduler():
    """Stop the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        print("Scheduler stopped")
