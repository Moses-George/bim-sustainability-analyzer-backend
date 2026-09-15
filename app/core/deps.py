"""Shared FastAPI dependencies: current user + project-level access control."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_sync_db
from app.core.security import decode_token
from app.models.user import User
from app.models.project import Project

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_sync_db)
) -> User:
    creds_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise creds_error
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise creds_error
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise creds_error
    return user


def get_optional_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_sync_db)
) -> User | None:
    """Same as get_current_user but returns None instead of 401 — used by
    endpoints (like chat) that work for anonymous callers but personalize
    when a valid token is present."""
    if not token:
        return None
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        return None
    user = db.get(User, int(payload["sub"]))
    return user if user and user.is_active else None


def get_owned_project(
    pid: int, db: Session = Depends(get_sync_db), user: User = Depends(get_current_user)
) -> Project:
    """A project is only ever visible to its owner."""
    project = db.get(Project, pid)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.owner_id != user.id:
        raise HTTPException(403, "You do not have access to this project")
    return project
