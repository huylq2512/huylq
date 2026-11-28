from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_auth_service, get_current_claims
from app.core.security import TokenClaims
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, service: AuthService = Depends(get_auth_service)):
    user = await service.register(data)
    return UserRead.from_user(user)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: AuthService = Depends(get_auth_service)):
    return await service.login(data)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    claims: TokenClaims = Depends(get_current_claims),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    await service.logout(claims)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
