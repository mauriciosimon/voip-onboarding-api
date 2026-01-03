from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, Token, UserResponse
from app.services.auth import (
    hash_password,
    authenticate_user,
    create_access_token,
    get_user_by_email,
)
from app.services.firewall import firewall_service, FirewallError

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    # Check X-Forwarded-For header (for proxies/load balancers)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user with existing SIP extension

    - Admin creates extension manually in FreePBX first
    - Then registers user here with email + SIP credentials
    - Returns user info (use /auth/login to get JWT)
    """
    # Check if email already exists
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if extension already registered
    existing_ext = db.query(User).filter(User.sip_extension == user_data.sip_extension).first()
    if existing_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extension already registered to another user"
        )

    # Create user in database
    db_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        sip_extension=user_data.sip_extension,
        sip_password=user_data.sip_password,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate user, whitelist IP, and return JWT token

    - Validates email/password
    - Adds user's IP to FreePBX firewall trusted zone
    - Returns access token for subsequent requests
    """
    user = authenticate_user(db, user_data.email, user_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get client IP and add to firewall (with 2-hour expiration)
    client_ip = get_client_ip(request)

    if client_ip and client_ip != "unknown":
        try:
            await firewall_service.trust_ip(client_ip, db, user_id=user.id)
        except FirewallError as e:
            # Log error but don't fail login
            print(f"Warning: Failed to whitelist IP {client_ip}: {e}")

    access_token = create_access_token(data={"sub": str(user.id)})

    return Token(access_token=access_token)
