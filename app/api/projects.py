"""Project CRUD + IFC ingestion. Every route is owner-scoped."""

from __future__ import annotations

import os
import tempfile
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_sync_db
from app.core.deps import get_current_user, get_owned_project
from app.models.project import Project
from app.models.user import User
from app.schemas.schemas import ProjectCreate, ProjectDetail, ProjectOut, TaskOut
from app.services.cloud_storage import CloudStorageError, upload_ifc_bytes
from app.services.ifc_parser import IfcParseError
from app.services.pipeline import ingest_ifc

router = APIRouter()


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
    """Upload the IFC straight to Cloudinary, then run the IfcOpenShell pipeline.

    The upload is never written to app-managed disk storage. IfcOpenShell's
    parser needs a filesystem path though, so for inline (non-Celery) parsing
    we hand it a short-lived temp file holding the same bytes we just sent to
    Cloudinary; that temp file is deleted immediately after parsing and is
    never treated as the file's storage location — Cloudinary is.
    """
    data = await file.read()
    filename = file.filename or "model.ifc"

    try:
        project.ifc_url = upload_ifc_bytes(data, filename)
    except CloudStorageError as exc:
        raise HTTPException(502, str(exc)) from exc
    db.commit()

    if settings.USE_CELERY:
        from app.worker.tasks import parse_ifc_task

        project.parse_status = "queued"
        db.commit()
        # Celery workers may run in a separate process/container, so the
        # task is handed the Cloudinary URL and downloads its own working
        # copy rather than sharing a local path with the API process.
        parse_ifc_task.delay(project.id, project.ifc_url)
        db.refresh(project)
        return project

    fd, tmp_path = tempfile.mkstemp(suffix=".ifc")
    try:
        with open(fd, "wb") as fh:
            fh.write(data)
        ingest_ifc(db, project, tmp_path)
    except IfcParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    return project


@router.get("/{pid}/status", response_model=TaskOut)
def parse_status(project: Project = Depends(get_owned_project)):
    return TaskOut(status=project.parse_status or "idle", project_id=project.id)
