from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any, Dict
from datetime import datetime

# ----------------------------------------------------------------- auth

class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    class Config: from_attributes = True

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# ------------------------------------------------------------ materials

class MaterialIn(BaseModel):
    name: str
    category: str
    embodied_carbon: float
    unit: str
    cost_per_unit: Optional[float] = None
    source: Optional[str] = None

class MaterialOut(MaterialIn):
    id: int
    class Config: from_attributes = True

# ------------------------------------------------------------- elements

class ElementOut(BaseModel):
    id: int
    global_id: Optional[str] = None
    ifc_type: Optional[str] = None
    name: Optional[str] = None
    storey: Optional[str] = None
    material: Optional[str] = None
    volume: Optional[float] = None
    area: Optional[float] = None
    embodied_carbon_kg: Optional[float] = None
    properties_json: Optional[Dict[str, Any]] = None
    bbox_json: Optional[Dict[str, Any]] = None
    class Config: from_attributes = True

# --------------------------------------------------------------- energy

class EnergyInputs(BaseModel):
    u_wall: float = 0.30
    u_roof: float = 0.20
    u_window: float = 1.60
    wwr: float = 0.35
    infiltration_ach: float = 0.45
    hvac_cop: float = 3.2
    heating_efficiency: float = 0.92
    lighting_power_density: Optional[float] = None
    grid_carbon_factor: float = 0.233

class EnergyOut(BaseModel):
    id: Optional[int] = None
    project_id: Optional[int] = None
    engine: Optional[str] = None
    heating_kwh: Optional[float] = None
    cooling_kwh: Optional[float] = None
    lighting_kwh: Optional[float] = None
    equipment_kwh: Optional[float] = None
    total_kwh: Optional[float] = None
    eui_kwh_m2: Optional[float] = None
    operational_carbon_kg: Optional[float] = None
    grid_factor_kg_kwh: Optional[float] = None
    monthly_json: Optional[Any] = None
    inputs_json: Optional[Any] = None
    class Config: from_attributes = True

# ------------------------------------------------------------- projects

class ProjectCreate(BaseModel):
    name: str
    building_type: Optional[str] = None
    climate_zone: Optional[str] = None
    floor_area: Optional[float] = None
    num_floors: Optional[int] = None

class ProjectOut(BaseModel):
    id: int
    owner_id: int
    name: str
    building_type: Optional[str] = None
    climate_zone: Optional[str] = None
    floor_area: Optional[float] = None
    num_floors: Optional[int] = None
    ifc_url: Optional[str] = None
    summary_json: Optional[Any] = None
    parse_status: Optional[str] = None
    parse_message: Optional[str] = None
    created_at: datetime
    class Config: from_attributes = True

class ProjectDetail(ProjectOut):
    elements: List[ElementOut] = []
    energy: Optional[EnergyOut] = None

class TaskOut(BaseModel):
    task_id: Optional[str] = None
    status: str
    project_id: int

# ------------------------------------------------------------------ AI

class RecommendationRequest(BaseModel):
    project_id: int
    target_reduction_pct: float = 20.0
    budget_flexibility_pct: float = 5.0

class Recommendation(BaseModel):
    title: str
    description: str
    carbon_reduction_pct: float
    cost_delta_pct: float
    category: str

class RecommendationResponse(BaseModel):
    project_id: int
    current_carbon_kg: float
    projected_carbon_kg: float
    recommendations: List[Recommendation]

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    project_id: Optional[int] = None
    messages: List[ChatMessage]

class ChatResponse(BaseModel):
    reply: str
