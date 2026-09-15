from sqlalchemy import Column, Integer, String, Float
from app.models.base import BaseModel

class Material(BaseModel):
    __tablename__ = "materials"
    name = Column(String(120), unique=True, nullable=False)
    category = Column(String(60), nullable=False)
    embodied_carbon = Column(Float, nullable=False)  # kgCO2 per unit
    unit = Column(String(20), nullable=False)        # m3 | ton | m2
    cost_per_unit = Column(Float)
    source = Column(String(300))                     # EPD / literature provenance
