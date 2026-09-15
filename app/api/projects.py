"""Project CRUD + IFC ingestion. Every route is owner-scoped."""

from __future__ import annotations

import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_sync_db
from app.core.deps import get_current_user, get_owned_project
from app.models.project import Project
from app.models.user import User
from app.schemas.schemas import ProjectCreate, ProjectDetail, ProjectOut, TaskOut
from app.services.ifc_parser import IfcParseError
from app.services.pipeline import ingest_ifc

router = APIRouter()


def _upload_to_cloudinary(path: str, filename: str) -> str | None:
    if not settings.CLOUDINARY_URL:
        return None
    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(cloudinary_url=settings.CLOUDINARY_URL)
        res = cloudinary.uploader.upload(
            path, resource_type="raw", public_id=f"ifc/{uuid.uuid4()}-{filename}"
        )
        return res.get("secure_url")
    except Exception:
        return None


@router.get("/", response_model=List[ProjectOut])
def list_projects(
    db: Session = Depends(get_sync_db), user: User = Depends(get_current_user)
):
    return (
        db.query(Project)
        .filter(Project.owner_id == user.id)
        .order_by(Project.id.desc())
        .all()
    )


@router.post("/", response_model=ProjectOut)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    project = Project(**data.model_dump(), owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{pid}", response_model=ProjectDetail)
def get_project(project: Project = Depends(get_owned_project)):
    return project


@router.delete("/{pid}")
def delete_project(
    project: Project = Depends(get_owned_project), db: Session = Depends(get_sync_db)
):
    db.delete(project)
    db.commit()
    return {"ok": True}


@router.post("/{pid}/upload-ifc", response_model=ProjectDetail)
async def upload_ifc(
    file: UploadFile = File(...),
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_sync_db),
):
    """Store the IFC, then run the IfcOpenShell pipeline (inline or via Celery)."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    stored = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4()}-{file.filename}")
    with open(stored, "wb") as fh:
        fh.write(await file.read())

    project.ifc_url = _upload_to_cloudinary(stored, file.filename or "model.ifc")

    if settings.USE_CELERY:
        from app.worker.tasks import parse_ifc_task

        project.parse_status = "queued"
        db.commit()
        parse_ifc_task.delay(project.id, stored)
        db.refresh(project)
        return project

    try:
        ingest_ifc(db, project, stored)
    except IfcParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        try:
            os.unlink(stored)
        except Exception:
            pass
    return project


@router.get("/{pid}/status", response_model=TaskOut)
def parse_status(project: Project = Depends(get_owned_project)):
    return TaskOut(status=project.parse_status or "idle", project_id=project.id)
