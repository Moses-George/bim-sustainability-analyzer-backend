from sqlalchemy.orm import Session
from app.models.material import Material

DEFAULT_FACTORS = {
    # Fallback only for materials with no catalogue match — kept in sync with
    # app.seed's cited ICE/EPD-derived figures rather than arbitrary numbers.
    "concrete": (360.0, "m3"),
    "steel": (1550.0, "ton"),
    "timber": (180.0, "m3"),
    "glass": (25.0, "m2"),
    "brick": (480.0, "m3"),
    "insulation": (30.0, "m3"),
    "aluminium": (12800.0, "ton"),
}


def factor_for(db: Session, material_name: str):
    if not material_name:
        return DEFAULT_FACTORS["concrete"]
    key = material_name.lower()
    m = db.query(Material).filter(Material.name.ilike(f"%{material_name}%")).first()
    if m:
        return m.embodied_carbon, m.unit
    for k, v in DEFAULT_FACTORS.items():
        if k in key:
            return v
    return DEFAULT_FACTORS["concrete"]


def compute_element_carbon(
    db: Session, material: str, volume: float | None, area: float | None
) -> float:
    factor, unit = factor_for(db, material or "")
    if unit == "m3" and volume:
        return factor * volume
    if unit == "m2" and area:
        return factor * area
    if unit == "ton" and volume:
        # rough: assume steel density 7.85 t/m3
        return factor * volume * 7.85
    return 0.0
