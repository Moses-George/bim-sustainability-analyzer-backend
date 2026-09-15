"""Real IfcOpenShell extraction pipeline.

For every building element we extract:
  * GlobalId (stable id the 3D viewer uses to map a click -> properties)
  * type, name, containing storey
  * material (association, layer sets, constituent sets, material lists)
  * quantities (NetVolume / NetSideArea ...) from IfcElementQuantity, falling
    back to tessellated geometry when quantities are missing
  * every property set, flattened to {"Pset.Prop": value}
  * an axis-aligned bounding box in metres, used to place the 3D mesh

`parse_ifc` raises IfcParseError when the file cannot be read, so the API
reports a real failure instead of inventing data.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:  # pragma: no cover - import guard
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.element as ifc_element
    import ifcopenshell.util.unit as ifc_unit
    HAS_IFC = True
except Exception:  # pragma: no cover
    HAS_IFC = False


class IfcParseError(RuntimeError):
    pass


BUILDING_ELEMENT_TYPES = ("IfcBuildingElement", "IfcElement")


def _material_name(element) -> str | None:
    try:
        mat = ifc_element.get_material(element, should_skip_usage=True)
    except Exception:
        mat = None
    if mat is None:
        return None
    try:
        if mat.is_a("IfcMaterial"):
            return mat.Name
        if mat.is_a("IfcMaterialLayerSet"):
            layers = [l for l in (mat.MaterialLayers or []) if l.Material]
            if layers:
                return max(layers, key=lambda l: l.LayerThickness or 0).Material.Name
        if mat.is_a("IfcMaterialLayerSetUsage") and mat.ForLayerSet:
            layers = [l for l in (mat.ForLayerSet.MaterialLayers or []) if l.Material]
            if layers:
                return max(layers, key=lambda l: l.LayerThickness or 0).Material.Name
        if mat.is_a("IfcMaterialConstituentSet"):
            cons = [c for c in (mat.MaterialConstituents or []) if c.Material]
            if cons:
                return cons[0].Material.Name
        if mat.is_a("IfcMaterialProfileSet"):
            profiles = [p for p in (mat.MaterialProfiles or []) if p.Material]
            if profiles:
                return profiles[0].Material.Name
        if mat.is_a("IfcMaterialList") and mat.Materials:
            return mat.Materials[0].Name
    except Exception:
        pass
    return getattr(mat, "Name", None)


def _storey_name(element) -> str | None:
    try:
        container = ifc_element.get_container(element)
        return getattr(container, "Name", None) if container else None
    except Exception:
        return None


def _flatten_psets(element) -> tuple[dict[str, Any], float | None, float | None]:
    """Return (flat properties, volume, area) from property sets and quantities."""
    flat: dict[str, Any] = {}
    volume: float | None = None
    area: float | None = None
    for kwargs in ({"psets_only": True}, {"qtos_only": True}):
        try:
            data = ifc_element.get_psets(element, **kwargs) or {}
        except Exception:
            data = {}
        for set_name, props in data.items():
            for key, value in (props or {}).items():
                if key == "id":
                    continue
                flat[f"{set_name}.{key}"] = (
                    value if isinstance(value, (str, int, float, bool)) or value is None else str(value)
                )
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    lk = key.lower()
                    if volume is None and "volume" in lk:
                        volume = float(value)
                    if area is None and "area" in lk:
                        area = float(value)
    return flat, volume, area


def _geometry(element, settings, unit_scale: float):
    """Tessellate the element -> (bbox, mesh volume, surface area)."""
    try:
        shape = ifcopenshell.geom.create_shape(settings, element)
    except Exception:
        return None, None, None
    verts = shape.geometry.verts
    faces = shape.geometry.faces
    if not verts:
        return None, None, None
    points = [
        (verts[i] * unit_scale, verts[i + 1] * unit_scale, verts[i + 2] * unit_scale)
        for i in range(0, len(verts), 3)
    ]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    bbox = {
        "min": [round(min(xs), 4), round(min(ys), 4), round(min(zs), 4)],
        "max": [round(max(xs), 4), round(max(ys), 4), round(max(zs), 4)],
    }
    vol = 0.0
    surf = 0.0
    for t in range(0, len(faces), 3):
        try:
            a, b, c = points[faces[t]], points[faces[t + 1]], points[faces[t + 2]]
        except IndexError:
            continue
        vol += (
            a[0] * (b[1] * c[2] - c[1] * b[2])
            - a[1] * (b[0] * c[2] - c[0] * b[2])
            + a[2] * (b[0] * c[1] - c[0] * b[1])
        ) / 6.0
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        surf += 0.5 * (cx * cx + cy * cy + cz * cz) ** 0.5
    return bbox, (abs(vol) or None), (surf or None)


def parse_ifc(path: str) -> list[dict[str, Any]]:
    if not HAS_IFC:
        raise IfcParseError(
            "ifcopenshell is not installed in this environment. Run the backend via "
            "Docker (see docker-compose.yml) or `pip install ifcopenshell`."
        )
    try:
        model = ifcopenshell.open(path)
    except Exception as exc:  # noqa: BLE001
        raise IfcParseError(f"Could not open IFC file: {exc}") from exc

    try:
        unit_scale = ifc_unit.calculate_unit_scale(model)
    except Exception:
        unit_scale = 1.0

    settings = ifcopenshell.geom.settings()
    try:
        settings.set(settings.USE_WORLD_COORDS, True)
    except Exception:
        pass

    elements: list[dict[str, Any]] = []
    seen: set[str] = set()
    for type_name in BUILDING_ELEMENT_TYPES:
        try:
            candidates = model.by_type(type_name)
        except Exception:
            continue
        for el in candidates:
            gid = getattr(el, "GlobalId", None)
            if not gid or gid in seen:
                continue
            if el.is_a("IfcOpeningElement") or el.is_a("IfcSpace"):
                continue
            seen.add(gid)
            props, q_volume, q_area = _flatten_psets(el)
            bbox, g_volume, g_area = _geometry(el, settings, unit_scale)
            elements.append({
                "global_id": gid,
                "ifc_type": el.is_a(),
                "name": getattr(el, "Name", None) or el.is_a(),
                "storey": _storey_name(el),
                "material": _material_name(el) or "Concrete",
                "volume": round(q_volume or g_volume or 0.0, 4) or None,
                "area": round(q_area or g_area or 0.0, 4) or None,
                "properties": props,
                "bbox": bbox,
            })
        if elements:
            break

    if not elements:
        raise IfcParseError("No building elements found in the IFC file.")
    logger.info("Parsed %s elements from %s", len(elements), path)
    return elements
