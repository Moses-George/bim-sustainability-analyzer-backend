from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_sync_db
from app.models.material import Material
from app.schemas.schemas import MaterialIn, MaterialOut
from app.seed import SEED

router = APIRouter()


@router.get("/", response_model=List[MaterialOut])
def list_materials(db: Session = Depends(get_sync_db)):
    if db.query(Material).count() == 0:
        for n, c, e, u, cost, source in SEED:
            db.add(
                Material(
                    name=n,
                    category=c,
                    embodied_carbon=e,
                    unit=u,
                    cost_per_unit=cost,
                    source=source,
                )
            )
        db.commit()
    return db.query(Material).order_by(Material.category, Material.name).all()


@router.post("/", response_model=MaterialOut)
def add_material(m: MaterialIn, db: Session = Depends(get_sync_db)):
    if db.query(Material).filter(Material.name == m.name).first():
        raise HTTPException(400, "exists")
    obj = Material(**m.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
