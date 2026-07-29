from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.auth import router as auth_router
from app.core.security import create_access_token, validate_password_policy
from app.core.config import Settings, settings
from app.db.base import Base
from app.db.session import get_db


def build_auth_test_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.dependency_overrides[get_db] = override_get_db
    app.include_router(auth_router)

    return TestClient(app)


def test_create_access_token_uses_utc_expiration():
    token = create_access_token(data={"sub": "phase0-user"}, expires_delta=timedelta(minutes=5))

    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

    assert payload["sub"] == "phase0-user"
    assert "exp" in payload


def test_register_and_login_return_valid_tokens():
    client = build_auth_test_client()
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "phase0-user", "password": "Phase0-password1!"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "phase0-user", "password": "Phase0-password1!"},
    )

    assert register_response.status_code == 201
    assert login_response.status_code == 200

    for response in (register_response, login_response):
        body = response.json()
        payload = jwt.decode(body["access_token"], settings.secret_key, algorithms=[settings.algorithm])
        assert body["token_type"] == "bearer"
        assert payload["sub"] == "phase0-user"


@pytest.mark.parametrize(
    "password",
    [
        "short",
        "password123",
        "12345678",
        "abcdefgh",
        " ValidPass1!",
        "ValidPass1! ",
        "a" * 73,
    ],
)
def test_password_policy_rejects_weak_values(password):
    with pytest.raises(ValueError):
        validate_password_policy(password)


def test_password_policy_accepts_mixed_password():
    validate_password_policy("ValidPass1!")


def test_register_rejects_weak_password():
    client = build_auth_test_client()
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "weak-user", "password": "12345678"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"secret_key": "supersecretkey", "api_key": "a" * 16, "allowed_origins": "https://example.com"},
        {"secret_key": "s" * 32, "api_key": "short", "allowed_origins": "https://example.com"},
        {"secret_key": "s" * 32, "api_key": "a" * 16, "allowed_origins": "*"},
    ],
)
def test_production_settings_reject_insecure_values(overrides):
    with pytest.raises(ValueError):
        Settings(environment="production", **overrides)


def test_production_settings_accept_secure_values():
    secure_settings = Settings(
        environment="production",
        secret_key="s" * 32,
        api_key="a" * 16,
        allowed_origins="https://example.com",
    )

    assert secure_settings.is_production
