from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_sync_db
from app.core.deps import get_current_user
from app.models.project import EnergyResult, Project
from app.models.user import User
from app.schemas.schemas import RecommendationRequest, RecommendationResponse
from app.services.recommender import recommend

router = APIRouter()


@router.post("/", response_model=RecommendationResponse)
def get_recommendations(
    req: RecommendationRequest,
    db: Session = Depends(get_sync_db),
    user: User = Depends(get_current_user),
):
    project = db.get(Project, req.project_id)
    if not project:
        raise HTTPException(404, "project not found")
    if project.owner_id != user.id:
        raise HTTPException(403, "You do not have access to this project")

    materials = {e.material for e in project.elements if e.material}
    recs = recommend(materials, req.target_reduction_pct)
    current = float((project.summary_json or {}).get("total_kg", 0.0))
    energy = db.query(EnergyResult).filter(EnergyResult.project_id == project.id).first()
    if energy and energy.operational_carbon_kg:
        # 30-year operational carbon included in the lifecycle baseline
        current += energy.operational_carbon_kg * 30
    projected = current * (1 - min(sum(r.carbon_reduction_pct for r in recs[:3]) / 100, 0.5))
    return RecommendationResponse(
        project_id=project.id,
        current_carbon_kg=current,
        projected_carbon_kg=projected,
        recommendations=recs,
    )
