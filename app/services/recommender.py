from typing import List
from app.schemas.schemas import Recommendation

RULES = [
    (
        "concrete",
        "Low-carbon concrete (30% GGBS)",
        "Replace OPC-based concrete mixes with GGBS/fly-ash blends.",
        22.0,
        3.0,
        "material",
    ),
    (
        "steel",
        "Use recycled structural steel",
        "Specify EAF recycled steel sections for beams and columns.",
        40.0,
        1.5,
        "material",
    ),
    (
        "glass",
        "Triple glazing with low-e coating",
        "Reduces operational energy demand for HVAC.",
        8.0,
        6.0,
        "envelope",
    ),
    (
        "timber",
        "Increase CLT use in floors",
        "Cross-laminated timber sequesters carbon.",
        18.0,
        4.0,
        "structure",
    ),
    (
        "insulation",
        "Bio-based insulation (hemp/wood-fibre)",
        "Lower embodied impact than XPS/EPS.",
        5.0,
        2.0,
        "envelope",
    ),
]


def recommend(materials_present: set[str], target_pct: float) -> List[Recommendation]:
    recs: List[Recommendation] = []
    for key, title, desc, red, cost, cat in RULES:
        if any(key in m.lower() for m in materials_present):
            recs.append(
                Recommendation(
                    title=title,
                    description=desc,
                    carbon_reduction_pct=red,
                    cost_delta_pct=cost,
                    category=cat,
                )
            )
    recs.append(
        Recommendation(
            title="Optimize structural grid",
            description="Generative design of column spacing reduces material quantities ~7%.",
            carbon_reduction_pct=7.0,
            cost_delta_pct=-1.0,
            category="structure",
        )
    )
    recs.append(
        Recommendation(
            title="Add PV + heat-pump",
            description="Reduces lifecycle operational carbon by up to 30% over 30 years.",
            carbon_reduction_pct=12.0,
            cost_delta_pct=5.0,
            category="energy",
        )
    )
    recs.sort(key=lambda r: -r.carbon_reduction_pct)
    return recs
