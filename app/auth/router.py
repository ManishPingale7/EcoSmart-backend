from fastapi import APIRouter, Request, HTTPException, status, Response, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
from datetime import timedelta
import httpx
from app.config import get_settings
from app.crud import authority as authority_crud
from app.crud import user as user_crud
from app.security import create_access_token, verify_token
from app.models import AuthorityCreate, Authority, AuthorityLogin, Token, GoogleUser

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/authority/login")


async def get_current_authority(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(token)
    if not payload:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    authority = await authority_crud.get_authority_by_username(username)
    if authority is None:
        raise credentials_exception
    return authority


@router.post("/authority/register", response_model=Authority)
async def register_authority(authority: AuthorityCreate):
    """Register a new authority"""
    return await authority_crud.create_authority(authority)


@router.post("/authority/login", response_model=Token)
async def authority_login(login_data: AuthorityLogin):
    """Authority login endpoint"""
    authority = await authority_crud.authenticate_authority(
        login_data.username,
        login_data.password
    )
    if not authority:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": authority["username"], "role": authority["role"]},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.get("/authority/me", response_model=Authority)
async def get_authority_info(current_authority: dict = Depends(get_current_authority)):
    """Get current authority information"""
    # Convert _id to id for Pydantic model
    authority_data = current_authority.copy()
    authority_data["id"] = str(authority_data.pop("_id"))
    return Authority(**authority_data)


@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth flow"""
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=email profile"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_callback(code: str):
    """Handle Google OAuth callback"""
    try:
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)
            token_response.raise_for_status()
            tokens = token_response.json()

            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )
            userinfo_response.raise_for_status()
            user_info = userinfo_response.json()

            # Get or create user
            user = await user_crud.get_or_create_google_user(user_info)
            
            # Prepare user data for the redirect
            user_data = {
                "email": user["email"],
                "name": user["name"],
                "picture": user.get("picture", "")
            }
            
            # Encode user data
            import base64
            import json
            encoded_data = base64.b64encode(json.dumps(user_data).encode()).decode()
            
            # Redirect to frontend with data
            frontend_url = "http://localhost:3000"
            return RedirectResponse(
                f"{frontend_url}/?success=true&user={encoded_data}",
                status_code=302
            )

    except Exception as e:
        # Redirect to frontend with error
        return RedirectResponse(
            f"http://localhost:3000/login?error={str(e)}",
            status_code=302
        )
