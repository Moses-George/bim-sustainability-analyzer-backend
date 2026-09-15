"""Background jobs: heavy IFC parsing and EnergyPlus simulations."""
from __future__ import annotations

import os

from app.core.database import SyncSessionLocal
from app.models.project import EnergyResult, Project
from app.services import energy as energy_service
from app.services.pipeline import ingest_ifc
from app.worker.celery_app import celery_app


@celery_app.task(name="ifc.parse")
def parse_ifc_task(project_id: int, path: str) -> dict:
    db = SyncSessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            return {"ok": False, "error": "project not found"}
        try:
            ingest_ifc(db, project, path)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "project_id": project_id, "elements": len(project.elements)}
    finally:
        db.close()
        try:
            os.unlink(path)
        except Exception:
            pass


@celery_app.task(name="energy.simulate")
def simulate_energy_task(project_id: int, inputs: dict) -> dict:
    db = SyncSessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            return {"ok": False, "error": "project not found"}
        result = energy_service.simulate(
            floor_area=project.floor_area,
            num_floors=project.num_floors,
            building_type=project.building_type,
            climate_zone=project.climate_zone,
            **inputs,
        )
        row = db.query(EnergyResult).filter(EnergyResult.project_id == project_id).first()
        if not row:
            row = EnergyResult(project_id=project_id)
            db.add(row)
        for key, value in result.items():
            setattr(row, key, value)
        db.commit()
        return {"ok": True, "project_id": project_id, "engine": result["engine"]}
    finally:
        db.close()
