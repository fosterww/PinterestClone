from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from auth.google_auth import verify_google_token
from auth.service import AuthService
from core.dependencies import get_auth_service
from core.security.auth import oauth2_scheme
from core.security.limiter import limiter
from users.schemas import GoogleLogin, TokenRefresh, UserCreate, UserResponse

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Register a new user."""
    user = await auth_service.register_user(data)
    return UserResponse.model_validate(user)


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Login with username and password."""
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tokens = await auth_service.create_user_session_and_tokens(user)
    return tokens


@router.post("/google")
@limiter.limit("5/minute")
async def login_google(
    request: Request,
    data: GoogleLogin,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Login with Google token."""
    google_info = await verify_google_token(data.id_token)
    if google_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await auth_service.get_or_create_google_user(google_info)
    tokens = await auth_service.create_user_session_and_tokens(user)
    return tokens


@router.post("/refresh")
@limiter.limit("5/minute")
async def refresh_token(
    request: Request,
    data: TokenRefresh,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Refresh access token."""
    tokens = await auth_service.refresh_user_token(data.refresh_token)
    return tokens


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
):
    await auth_service.logout_user(token)
    return {"message": "Logged out successfully"}
