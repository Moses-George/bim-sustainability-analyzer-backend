from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_sync_db
from app.ml.predictor import predict, retrain
from pydantic import BaseModel

router = APIRouter()


class PredictIn(BaseModel):
    area: float
    floors: int
    concrete_ratio: float = 0.6
    steel_ratio: float = 0.2
    timber_ratio: float = 0.2


@router.post("/predict-carbon")
def predict_carbon(p: PredictIn, db: Session = Depends(get_sync_db)):
    kg = predict(
        p.area, p.floors, p.concrete_ratio, p.steel_ratio, p.timber_ratio, db=db
    )
    return {"predicted_embodied_carbon_kg": kg, "tonnes": kg / 1000}


@router.post("/predict-carbon/retrain")
def retrain_model(db: Session = Depends(get_sync_db)):
    """Refit against whatever real parsed projects exist right now."""
    _, n_real, n_prior = retrain(db)
    return {"trained_on_real_projects": n_real, "trained_on_prior_samples": n_prior}
