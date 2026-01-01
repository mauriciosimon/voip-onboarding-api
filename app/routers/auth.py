from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, Token, UserResponse
from app.services.auth import (
    hash_password,
    authenticate_user,
    create_access_token,
    get_user_by_email,
    get_next_extension,
)
from app.services.freepbx import freepbx_service, FreePBXError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user and create SIP extension in FreePBX

    - Creates user account with email/password
    - Auto-generates next available extension number
    - Creates extension in FreePBX with secure password
    - Returns user info (use /auth/login to get JWT)
    """
    # Check if email already exists
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Get next available extension
    extension = get_next_extension(db)

    # Create extension in FreePBX
    try:
        freepbx_result = await freepbx_service.create_extension(
            extension=extension,
            name=user_data.email.split("@")[0],  # Use email prefix as name
        )
    except FreePBXError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to create SIP extension: {str(e)}"
        )

    # Create user in database
    db_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        sip_extension=extension,
        sip_password=freepbx_result["password"],
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT token

    - Validates email/password
    - Returns access token for subsequent requests
    """
    user = authenticate_user(db, user_data.email, user_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.id})

    return Token(access_token=access_token)
