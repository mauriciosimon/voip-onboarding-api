from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import SIPCredentials
from app.config import get_settings

router = APIRouter(prefix="/sip", tags=["SIP Configuration"])

settings = get_settings()


@router.get("/credentials", response_model=SIPCredentials)
async def get_sip_credentials(current_user: User = Depends(get_current_user)):
    """
    Get SIP credentials for the authenticated user

    Returns all information needed to configure a SIP softphone (Linphone, etc.):
    - Username (extension number)
    - Password
    - Domain/Server
    - Port
    - Transport protocol
    """
    return SIPCredentials(
        username=current_user.sip_extension,
        password=current_user.sip_password,
        domain=settings.sip_domain,
        port=settings.sip_port,
        transport=settings.sip_transport,
        display_name=current_user.email.split("@")[0],
        auth_username=current_user.sip_extension,
    )
