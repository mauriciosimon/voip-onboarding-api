import asyncio
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.database import SessionLocal
from app.services.firewall import firewall_service

# Scheduler instance
scheduler = AsyncIOScheduler()


async def cleanup_expired_ips_job():
    """Background job to remove expired IPs from firewall"""
    print("Running IP cleanup job...")
    db = SessionLocal()
    try:
        removed = await firewall_service.cleanup_expired_ips(db)
        if removed:
            print(f"Cleaned up {len(removed)} expired IPs: {removed}")
        else:
            print("No expired IPs to clean up")
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
