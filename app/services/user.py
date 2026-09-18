from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRequest, UserUpdateRequest
from app.services.base import BaseService


class UserAlreadyExistsError(Exception):
    """Raised when an email is already registered to another user."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials don't match an existing user."""


class UserService(BaseService[User, UserRequest, UserUpdateRequest]):
    def __init__(self, repository: UserRepository) -> None:
        super().__init__(repository)
        self.repository: UserRepository = repository

    async def create(self, data: UserRequest) -> User:
        if await self.repository.get_by_email(data.email) is not None:
            raise UserAlreadyExistsError(data.email)

        return await self.repository.create(
            email=data.email,
            password_hash=hash_password(data.password),
            name=data.name,
        )

    async def update(self, obj: User, data: UserUpdateRequest) -> User:
        if data.email is not None and data.email != obj.email:
            existing = await self.repository.get_by_email(data.email)
            if existing is not None and existing.id != obj.id:
                raise UserAlreadyExistsError(data.email)

        return await super().update(obj, data)

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.repository.get_by_email(data.email)
        if user is None or not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError()

        return TokenResponse(
            access_token=create_access_token(subject=user.id),
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
