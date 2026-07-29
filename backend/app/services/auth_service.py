from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.repositories.user_repository import create_user, get_user_by_username


def register_user(db: Session, username: str, password: str) -> dict[str, str]:
    if get_user_by_username(db, username):
        raise HTTPException(status_code=400, detail="Username already registered")

    user = create_user(db, username=username, hashed_password=get_password_hash(password))
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "username": user.username}


def authenticate_user(db: Session, username: str, password: str) -> dict[str, str]:
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "username": user.username}
