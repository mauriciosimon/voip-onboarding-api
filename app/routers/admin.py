from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models.user import User
from app.models.trusted_ip import TrustedIP
from app.models.ssh_account import SSHAccount
from app.models.admin_user import AdminUser
from app.config import get_settings
from app.services.auth import hash_password, verify_password

settings = get_settings()

router = APIRouter(prefix="/admin", tags=["Admin"])


class AdminLogin(BaseModel):
    username: str
    password: str


class AdminToken(BaseModel):
    success: bool
    message: str
    username: str


class SSHAccountCreate(BaseModel):
    name: str
    host: str
    ssh_user: str = "root"
    ssh_key_path: str


class SSHAccountOut(BaseModel):
    id: int
    name: str
    host: str
    ssh_user: str
    ssh_key_path: str

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    sip_extension: str
    sip_password: str
    account_id: Optional[int] = None


class UserOut(BaseModel):
    id: int
    email: str
    sip_extension: str
    is_active: bool
    account_id: Optional[int] = None
    account_name: Optional[str] = None

    class Config:
        from_attributes = True


class TrustedIPOut(BaseModel):
    id: int
    ip_address: str
    user_id: int | None
    created_at: str
    expires_at: str

    class Config:
        from_attributes = True


class AdminUserCreate(BaseModel):
    username: str
    password: str


class AdminUserOut(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


def verify_admin_credentials(db: Session, username: str, password: str) -> AdminUser | None:
    """Verify admin username and password"""
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if admin and verify_password(password, admin.hashed_password):
        return admin
    return None


def verify_admin_auth(db: Session, username: str, password: str) -> bool:
    """Simple auth check for API endpoints"""
    return verify_admin_credentials(db, username, password) is not None


@router.post("/login", response_model=AdminToken)
async def admin_login(data: AdminLogin, db: Session = Depends(get_db)):
    """Admin login - verify username and password"""
    admin = verify_admin_credentials(db, data.username, data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    return AdminToken(success=True, message="Admin authenticated", username=admin.username)


@router.post("/setup", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def setup_first_admin(new_admin: AdminUserCreate, db: Session = Depends(get_db)):
    """Create the first admin user (only works when no admins exist)"""
    # Check if any admin exists
    if db.query(AdminUser).count() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin already exists. Use /admin/login to access."
        )

    db_admin = AdminUser(
        username=new_admin.username,
        hashed_password=hash_password(new_admin.password),
    )
    db.add(db_admin)
    db.commit()
    db.refresh(db_admin)
    return db_admin


@router.get("/users")
async def list_users(admin_user: str, admin_pass: str, db: Session = Depends(get_db)):
    """List all users (requires admin credentials)"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "sip_extension": u.sip_extension,
            "is_active": u.is_active,
            "account_id": u.account_id,
            "account_name": u.ssh_account.name if u.ssh_account else None,
        }
        for u in users
    ]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    admin_user: str,
    admin_pass: str,
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Create a new user (admin only)"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )

    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if extension exists
    if db.query(User).filter(User.sip_extension == user_data.sip_extension).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extension already registered"
        )

    # Validate account_id if provided
    if user_data.account_id:
        account = db.query(SSHAccount).filter(SSHAccount.id == user_data.account_id).first()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SSH Account not found"
            )

    db_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        sip_extension=user_data.sip_extension,
        sip_password=user_data.sip_password,
        account_id=user_data.account_id,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {
        "id": db_user.id,
        "email": db_user.email,
        "sip_extension": db_user.sip_extension,
        "is_active": db_user.is_active,
        "account_id": db_user.account_id,
        "account_name": db_user.ssh_account.name if db_user.ssh_account else None,
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: str,
    admin_pass: str,
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()
    return {"message": f"User {user.email} deleted"}


@router.get("/trusted-ips")
async def list_trusted_ips(admin_user: str, admin_pass: str, db: Session = Depends(get_db)):
    """List all trusted IPs in database"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )

    ips = db.query(TrustedIP).all()
    return [
        {
            "id": ip.id,
            "ip_address": ip.ip_address,
            "user_id": ip.user_id,
            "created_at": ip.created_at.isoformat() if ip.created_at else None,
            "expires_at": ip.expires_at.isoformat() if ip.expires_at else None,
        }
        for ip in ips
    ]


@router.get("/ssh-config")
async def get_ssh_config(admin_user: str, admin_pass: str, db: Session = Depends(get_db)):
    """Get current SSH configuration from .env (legacy)"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )

    return {
        "freepbx_host": settings.freepbx_host,
        "ssh_user": settings.ssh_user,
        "ssh_key_path": settings.ssh_key_path,
    }


# ============== SSH Accounts ==============

@router.get("/accounts", response_model=List[SSHAccountOut])
async def list_accounts(admin_user: str, admin_pass: str, db: Session = Depends(get_db)):
    """List all SSH accounts"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )
    return db.query(SSHAccount).all()


@router.post("/accounts", response_model=SSHAccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    admin_user: str,
    admin_pass: str,
    account_data: SSHAccountCreate,
    db: Session = Depends(get_db)
):
    """Create a new SSH account"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )

    # Check if name exists
    if db.query(SSHAccount).filter(SSHAccount.name == account_data.name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account name already exists"
        )

    db_account = SSHAccount(
        name=account_data.name,
        host=account_data.host,
        ssh_user=account_data.ssh_user,
        ssh_key_path=account_data.ssh_key_path,
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: int,
    admin_user: str,
    admin_pass: str,
    db: Session = Depends(get_db)
):
    """Delete an SSH account"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )

    account = db.query(SSHAccount).filter(SSHAccount.id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )

    # Check if any users are using this account
    users_count = db.query(User).filter(User.account_id == account_id).count()
    if users_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete: {users_count} user(s) are using this account"
        )

    db.delete(account)
    db.commit()
    return {"message": f"Account '{account.name}' deleted"}


# ============== Admin Users ==============

@router.get("/admin-users", response_model=List[AdminUserOut])
async def list_admin_users(admin_user: str, admin_pass: str, db: Session = Depends(get_db)):
    """List all admin users"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )
    return db.query(AdminUser).all()


@router.post("/admin-users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    admin_user: str,
    admin_pass: str,
    new_admin: AdminUserCreate,
    db: Session = Depends(get_db)
):
    """Create a new admin user"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )

    # Check if username exists
    if db.query(AdminUser).filter(AdminUser.username == new_admin.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    db_admin = AdminUser(
        username=new_admin.username,
        hashed_password=hash_password(new_admin.password),
    )
    db.add(db_admin)
    db.commit()
    db.refresh(db_admin)
    return db_admin


@router.delete("/admin-users/{admin_id}")
async def delete_admin_user(
    admin_id: int,
    admin_user: str,
    admin_pass: str,
    db: Session = Depends(get_db)
):
    """Delete an admin user"""
    if not verify_admin_auth(db, admin_user, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )

    # Prevent deleting the last admin
    admin_count = db.query(AdminUser).count()
    if admin_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last admin user"
        )

    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found"
        )

    db.delete(admin)
    db.commit()
    return {"message": f"Admin '{admin.username}' deleted"}
