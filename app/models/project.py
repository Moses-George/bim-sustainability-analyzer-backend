from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, DateTime, JSON, func,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Project(BaseModel):
    __tablename__ = "projects"
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(200), nullable=False)
    building_type = Column(String(60))
    climate_zone = Column(String(60))
    floor_area = Column(Float)
    num_floors = Column(Integer)
    ifc_url = Column(String(500))
    summary_json = Column(JSON)
    parse_status = Column(String(30), default="idle")   # idle | queued | running | done | failed
    parse_message = Column(String(500))

    owner = relationship("User", back_populates="projects")
    elements = relationship("Element", back_populates="project", cascade="all, delete-orphan")
    energy = relationship(
        "EnergyResult", back_populates="project", cascade="all, delete-orphan", uselist=False
    )


class Element(BaseModel):
    __tablename__ = "elements"
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    global_id = Column(String(64), index=True)          # IfcRoot.GlobalId - stable click target
    ifc_type = Column(String(80))
    name = Column(String(200))
    storey = Column(String(120))
    material = Column(String(120))
    volume = Column(Float)
    area = Column(Float)
    embodied_carbon_kg = Column(Float)
    properties_json = Column(JSON)                      # flattened IFC property sets
    bbox_json = Column(JSON)                            # {min:[x,y,z], max:[x,y,z]} in metres

    project = relationship("Project", back_populates="elements")


class EnergyResult(BaseModel):
    __tablename__ = "energy_results"
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True, unique=True)
    engine = Column(String(40))                         # energyplus | iso13790-fallback
    heating_kwh = Column(Float)
    cooling_kwh = Column(Float)
    lighting_kwh = Column(Float)
    equipment_kwh = Column(Float)
    total_kwh = Column(Float)
    eui_kwh_m2 = Column(Float)
    operational_carbon_kg = Column(Float)
    grid_factor_kg_kwh = Column(Float)
    monthly_json = Column(JSON)                         # [{month, heating, cooling, lighting}]
    inputs_json = Column(JSON)

    project = relationship("Project", back_populates="energy")
