from pydantic import BaseModel, Field, field_validator

from app.core.security import validate_password_policy


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_must_meet_policy(cls, value: str) -> str:
        try:
            validate_password_policy(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return value
