from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest
from app.schemas.user import UserRequest, UserUpdateRequest
from app.services.user import InvalidCredentialsError, UserAlreadyExistsError, UserService


@pytest.fixture
def service(db_session: AsyncSession) -> UserService:
    return UserService(UserRepository(db_session))


async def test_create_hashes_the_password(service: UserService) -> None:
    user = await service.create(
        UserRequest(email="andre@example.com", password="supersecret", name="Andre")
    )

    assert user.password_hash != "supersecret"


async def test_create_rejects_duplicate_email(service: UserService) -> None:
    await service.create(
        UserRequest(email="andre@example.com", password="supersecret", name="Andre")
    )

    with pytest.raises(UserAlreadyExistsError):
        await service.create(
            UserRequest(email="andre@example.com", password="whatever1", name="Other")
        )


async def test_update_name_only(service: UserService) -> None:
    user = await service.create(
        UserRequest(email="andre@example.com", password="supersecret", name="Andre")
    )

    updated = await service.update(user, UserUpdateRequest(name="Andre B"))

    assert updated.name == "Andre B"
    assert updated.email == "andre@example.com"


async def test_update_to_own_current_email_is_not_a_conflict(service: UserService) -> None:
    user = await service.create(
        UserRequest(email="andre@example.com", password="supersecret", name="Andre")
    )

    updated = await service.update(user, UserUpdateRequest(email="andre@example.com"))

    assert updated.email == "andre@example.com"


async def test_update_to_another_users_email_is_rejected(service: UserService) -> None:
    user = await service.create(
        UserRequest(email="andre@example.com", password="supersecret", name="Andre")
    )
    await service.create(
        UserRequest(email="other@example.com", password="whatever1", name="Other")
    )

    with pytest.raises(UserAlreadyExistsError):
        await service.update(user, UserUpdateRequest(email="other@example.com"))


async def test_login_returns_a_token_for_the_correct_user(service: UserService) -> None:
    user = await service.create(
        UserRequest(email="andre@example.com", password="supersecret", name="Andre")
    )

    token_response = await service.login(
        LoginRequest(email="andre@example.com", password="supersecret")
    )

    payload = decode_access_token(token_response.access_token)
    assert int(payload["sub"]) == user.id

    assert token_response.expires_in == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    expected_expiry = datetime.now(UTC).timestamp() + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert payload["exp"] == pytest.approx(expected_expiry, abs=5)


async def test_login_rejects_wrong_password(service: UserService) -> None:
    await service.create(
        UserRequest(email="andre@example.com", password="supersecret", name="Andre")
    )

    with pytest.raises(InvalidCredentialsError):
        await service.login(LoginRequest(email="andre@example.com", password="wrongpassword"))


async def test_login_rejects_unknown_email(service: UserService) -> None:
    with pytest.raises(InvalidCredentialsError):
        await service.login(LoginRequest(email="nobody@example.com", password="whatever1"))
