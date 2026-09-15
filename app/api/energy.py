"""Operational energy endpoints (EnergyPlus-backed)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_sync_db
from app.core.deps import get_owned_project
from app.models.project import EnergyResult, Project
from app.schemas.schemas import EnergyInputs, EnergyOut
from app.services import energy as energy_service

router = APIRouter()


@router.get("/{pid}", response_model=EnergyOut)
def get_energy(project: Project = Depends(get_owned_project), db: Session = Depends(get_sync_db)):
    row = db.query(EnergyResult).filter(EnergyResult.project_id == project.id).first()
    if not row:
        raise HTTPException(404, "No energy simulation has been run for this project yet")
    return row


@router.post("/{pid}/simulate", response_model=EnergyOut)
def run_simulation(
    inputs: EnergyInputs | None = None,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_sync_db),
):
    payload = (inputs or EnergyInputs()).model_dump()

    if settings.USE_CELERY:
        from app.worker.tasks import simulate_energy_task

        simulate_energy_task.apply_async(args=[project.id, payload])

    result = energy_service.simulate(
        floor_area=project.floor_area,
        num_floors=project.num_floors,
        building_type=project.building_type,
        climate_zone=project.climate_zone,
        weather_file=settings.EPW_FILE,
        **payload,
    )
    row = db.query(EnergyResult).filter(EnergyResult.project_id == project.id).first()
    if not row:
        row = EnergyResult(project_id=project.id)
        db.add(row)
    for key, value in result.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.get("/engine/info")
def engine_info():
    return {
        "energyplus_available": energy_service.energyplus_available(),
        "fallback": "iso13790-fallback",
    }
