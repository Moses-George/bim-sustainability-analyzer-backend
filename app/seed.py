"""Seed the carbon material database with real, cited embodied-carbon
coefficients (cradle-to-gate, EN 15804 modules A1-A3) instead of made-up
numbers.

IMPORTANT LICENSING NOTE: the ICE (Inventory of Carbon & Energy) database
from the University of Bath / Circular Ecology may not be redistributed or
re-uploaded ("must not be distributed nor uploaded to websites without the
written permission of the authors" - circularecology.com). Ecoinvent is a
paid, licensed LCA dataset with its own redistribution restrictions. So
instead of bulk-copying either database into this repo, each row below is a
small, individually-sourced, widely-published per-kg coefficient (the kind
that appears identically across ICE-derived calculators, EPDs and academic
LCAs), converted to the app's per-m3/per-ton/per-m2 units using standard
material densities. That keeps the app's numbers realistic and citable
without redistributing a licensed dataset.

For production use, wire this up to a licensed ICE download or to specific
product EPDs (EN 15804) from your suppliers via the `source` field, which is
exactly what it's there for - swap these generic figures for
project-specific EPDs as you get them.

Run standalone:  python -m app.seed
"""

from app.core.database import Base, SyncSessionLocal, sync_engine
from app.models.material import Material
from app.models import user
from app.models import project  # noqa: F401

ICE = "ICE v4.1-derived (Univ. of Bath / Circular Ecology), cradle-to-gate A1-A3"
WORLDSTEEL = "worldsteel / regional EPD average, cradle-to-gate A1-A3"

# (name, category, kgCO2e/unit, unit, cost/unit, source)
# Concrete & steel densities: 2400 kg/m3 concrete, 7850 kg/m3 steel (unit "ton" = 1000 kg)
# Timber ~470-480 kg/m3, clay brick ~1900 kg/m3, mineral wool ~24 kg/m3 (batt)
SEED = [
    (
        "Concrete C30",
        "concrete",
        360,
        "m3",
        120,
        f"{ICE}: ~0.15 kgCO2e/kg x 2400 kg/m3",
    ),
    (
        "Concrete C40",
        "concrete",
        400,
        "m3",
        138,
        f"{ICE}: ~0.17 kgCO2e/kg x 2400 kg/m3",
    ),
    (
        "Low-carbon Concrete (30% GGBS)",
        "concrete",
        250,
        "m3",
        135,
        f"{ICE}: GGBS cement replacement, ~30% reduction vs C30",
    ),
    (
        "Recycled Aggregate Concrete",
        "concrete",
        320,
        "m3",
        128,
        f"{ICE}: recycled coarse aggregate, modest reduction vs C30",
    ),
    (
        "Structural Steel (virgin, BOF route)",
        "steel",
        1550,
        "ton",
        900,
        f"{WORLDSTEEL}: ~1.55 kgCO2e/kg general structural steel",
    ),
    (
        "Recycled Steel (EAF, high recycled content)",
        "steel",
        500,
        "ton",
        950,
        f"{WORLDSTEEL}: ~0.45-0.5 kgCO2e/kg EAF recycled steel",
    ),
    (
        "Reinforcement Bar",
        "steel",
        1990,
        "ton",
        820,
        f"{WORLDSTEEL}: ~1.99 kgCO2e/kg average rebar EPD",
    ),
    (
        "CLT Timber",
        "timber",
        180,
        "m3",
        700,
        f"{ICE}: ~0.38 kgCO2e/kg structural timber x 470 kg/m3 (excludes biogenic storage credit)",
    ),
    (
        "Glulam Timber",
        "timber",
        210,
        "m3",
        760,
        f"{ICE}: ~0.44 kgCO2e/kg (adhesive/processing) x 480 kg/m3",
    ),
    (
        "Clay Brick",
        "brick",
        480,
        "m3",
        210,
        f"{ICE}: ~0.25 kgCO2e/kg fired clay brick x 1900 kg/m3",
    ),
    (
        "Double Glazing",
        "glass",
        25,
        "m2",
        180,
        f"{ICE}: ~0.85 kgCO2e/kg float glass, typical IGU per m2",
    ),
    (
        "Triple Glazing",
        "glass",
        42,
        "m2",
        260,
        f"{ICE}: extra pane + low-e coating, typical IGU per m2",
    ),
    (
        "Mineral Wool Insulation",
        "insulation",
        30,
        "m3",
        70,
        f"{ICE}: ~1.28 kgCO2e/kg x 24 kg/m3 batt density",
    ),
    (
        "Hemp Insulation",
        "insulation",
        15,
        "m3",
        90,
        f"{ICE}: bio-based, processing-only figure (excludes biogenic credit)",
    ),
    (
        "Aluminium Cladding (primary)",
        "aluminium",
        12800,
        "ton",
        3200,
        f"{ICE}: ~13.1 kgCO2e/kg primary aluminium",
    ),
    (
        "Aluminium Cladding (recycled)",
        "aluminium",
        500,
        "ton",
        3600,
        f"{ICE}: ~0.5 kgCO2e/kg secondary/recycled aluminium (~4% of primary)",
    ),
]


def run() -> int:
    Base.metadata.create_all(bind=sync_engine)
    db = SyncSessionLocal()
    added = 0
    try:
        for name, category, ec, unit, cost, source in SEED:
            existing = db.query(Material).filter(Material.name == name).first()
            if existing:
                # keep numbers current if a material's figure was updated
                existing.embodied_carbon = ec
                existing.unit = unit
                existing.cost_per_unit = cost
                existing.source = source
                continue
            db.add(
                Material(
                    name=name,
                    category=category,
                    embodied_carbon=ec,
                    unit=unit,
                    cost_per_unit=cost,
                    source=source,
                )
            )
            added += 1
        db.commit()
    finally:
        db.close()
    return added


if __name__ == "__main__":
    print(f"Seeded {run()} materials")
