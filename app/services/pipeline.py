"""Shared IFC -> database pipeline used by both the API and the Celery worker."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.project import Element, Project
from app.services.carbon import compute_element_carbon
from app.services.ifc_parser import IfcParseError, parse_ifc


def ingest_ifc(db: Session, project: Project, path: str) -> Project:
    """Parse an IFC file and persist elements, properties and carbon."""
    project.parse_status = "running"
    project.parse_message = None
    db.commit()

    try:
        parsed = parse_ifc(path)
    except IfcParseError as exc:
        project.parse_status = "failed"
        project.parse_message = str(exc)
        db.commit()
        raise

    db.query(Element).filter(Element.project_id == project.id).delete()

    totals: dict = {"total_kg": 0.0, "by_material": {}, "by_type": {}, "element_count": len(parsed)}
    for item in parsed:
        carbon = compute_element_carbon(db, item.get("material"), item.get("volume"), item.get("area"))
        db.add(Element(
            project_id=project.id,
            global_id=item.get("global_id"),
            ifc_type=item.get("ifc_type"),
            name=item.get("name"),
            storey=item.get("storey"),
            material=item.get("material"),
            volume=item.get("volume"),
            area=item.get("area"),
            embodied_carbon_kg=carbon,
            properties_json=item.get("properties"),
            bbox_json=item.get("bbox"),
        ))
        totals["total_kg"] += carbon
        mat = item.get("material") or "Unknown"
        typ = item.get("ifc_type") or "Unknown"
        totals["by_material"][mat] = totals["by_material"].get(mat, 0.0) + carbon
        totals["by_type"][typ] = totals["by_type"].get(typ, 0.0) + carbon

    project.summary_json = totals
    project.parse_status = "done"
    project.parse_message = f"Extracted {len(parsed)} elements"
    db.commit()
    db.refresh(project)
    return project
