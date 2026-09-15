"""XGBoost embodied-carbon predictor.

Real training data path: once you have parsed a handful of real IFC projects
(app.models.project.Project.summary_json + floor_area/num_floors), this pulls
their (area, floors, material-mix ratio) -> actual total_kg pairs straight out
of the database and trains on that.

Because a fresh install has zero real projects, we still need a model to
serve predictions from day one. The bootstrap prior below is NOT random noise
- it's the same area x carbon-intensity-per-material physics used by
app.services.carbon (concrete/steel/timber intensities in kg CO2e per m3/ton),
so early predictions are physically sane. As real projects accumulate, retrain()
blends them in and the model converges toward your actual building stock
instead of the prior.

MIN_REAL_SAMPLES gates when we trust the DB data alone; below that we still
mix in the prior so a couple of early projects can't overfit the model.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import xgboost as xgb
from sqlalchemy.orm import Session

MIN_REAL_SAMPLES = 25

# kg CO2e per unit, matching app.services.carbon.DEFAULT_FACTORS
CONCRETE_KG_M3 = 300.0
STEEL_KG_TON = 1900.0
TIMBER_KG_M3 = 110.0
STEEL_DENSITY_T_M3 = 7.85

_model: xgb.XGBRegressor | None = None
_trained_on = 0  # sample count the cached model was fit on, to know when to retrain


@dataclass
class Sample:
    area: float
    floors: int
    concrete_ratio: float
    steel_ratio: float
    timber_ratio: float
    total_kg: float


def _bootstrap_prior(n: int = 800, seed: int = 42) -> list[Sample]:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        area = rng.uniform(200, 20000)
        floors = int(rng.integers(1, 40))
        concrete_ratio = rng.uniform(0.2, 0.8)
        steel_ratio = rng.uniform(0.05, 0.4)
        timber_ratio = max(0.0, 1 - concrete_ratio - steel_ratio)
        # same physics as app.services.carbon: per-m3 concrete/timber factors,
        # per-ton steel factor converted via density, scaled by floor area
        # and a mild high-rise structural-efficiency penalty.
        y = area * (
            CONCRETE_KG_M3 * concrete_ratio
            + STEEL_KG_TON * STEEL_DENSITY_T_M3 * 0.02 * steel_ratio
            + TIMBER_KG_M3 * timber_ratio
        ) * (1 + 0.015 * floors)
        out.append(Sample(area, floors, concrete_ratio, steel_ratio, timber_ratio, y))
    return out


def _real_samples(db: Session) -> list[Sample]:
    """Pull (area, floors, material mix, actual total) from projects that
    have already been through the real ifcopenshell parse pipeline."""
    from app.models.project import Project  # local import: avoid circular import

    out: list[Sample] = []
    projects = (
        db.query(Project)
        .filter(Project.parse_status == "done", Project.summary_json.isnot(None))
        .all()
    )
    for p in projects:
        summary = p.summary_json or {}
        total_kg = summary.get("total_kg")
        by_material = summary.get("by_material") or {}
        if not total_kg or not p.floor_area or not by_material:
            continue

        def ratio(keys: tuple[str, ...]) -> float:
            matched = sum(v for k, v in by_material.items() if any(kk in k.lower() for kk in keys))
            return matched / total_kg if total_kg else 0.0

        out.append(Sample(
            area=float(p.floor_area),
            floors=int(p.num_floors or 1),
            concrete_ratio=ratio(("concrete",)),
            steel_ratio=ratio(("steel", "rebar", "reinforcement")),
            timber_ratio=ratio(("timber", "wood", "clt", "glulam")),
            total_kg=float(total_kg),
        ))
    return out


def _fit(samples: list[Sample]) -> xgb.XGBRegressor:
    X = np.array([[s.area, s.floors, s.concrete_ratio, s.steel_ratio, s.timber_ratio] for s in samples])
    y = np.array([s.total_kg for s in samples])
    model = xgb.XGBRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.08,
        subsample=0.9, colsample_bytree=0.9, random_state=0,
    )
    model.fit(X, y)
    return model


def retrain(db: Session | None = None) -> tuple[xgb.XGBRegressor, int, int]:
    """Rebuild the model. Returns (model, n_real_samples_used, n_prior_samples_used)."""
    global _model, _trained_on
    real = _real_samples(db) if db is not None else []
    if len(real) >= MIN_REAL_SAMPLES:
        # Enough real buildings: train on real data only.
        samples, n_prior = real, 0
    else:
        # Blend: keep the physics prior in the mix so a handful of real
        # projects nudge the model without letting it overfit to them.
        samples, n_prior = real + _bootstrap_prior(), len(_bootstrap_prior())
    _model = _fit(samples)
    _trained_on = len(samples)
    return _model, len(real), n_prior


def predict(
    area: float, floors: int, concrete_ratio: float, steel_ratio: float,
    timber_ratio: float, db: Session | None = None,
) -> float:
    global _model
    if _model is None:
        retrain(db)
    x = np.array([[area, floors, concrete_ratio, steel_ratio, timber_ratio]])
    return float(_model.predict(x)[0])
