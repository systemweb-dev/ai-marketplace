"""Validation contract for flow.json documents."""

from __future__ import annotations

import math
import re
from typing import Any

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
LAYOUTS = {"flow", "tiers", "graph"}
DIRECTIONS = {"LR", "TB"}
ANIMATION_MODES = {"packet", "highlight", "draw", "none"}
SHAPES = {
    "rounded", "rect", "stadium", "diamond", "parallel", "cylinder", "circle",
    "hexagon", "document", "docs", "subroutine", "manual", "operation", "delay",
    "display", "storage", "merge", "extract", "offpage", "cloud", "note",
}
STYLES = {"solid", "dashed"}
SIDES = {"left", "right", "top", "bottom"}
ICONS = {
    "user", "server", "database", "storage", "queue", "cache", "shield", "cloud", "balancer",
    "gateway", "gear", "service", "document", "message", "mobile", "browser", "lock", "clock",
    "decision", "external", "api", "globe", "proxy", "cdn", "firewall", "function", "container",
    "search", "monitor", "box", "none",
    "brain", "chat", "money", "truck", "key", "flask", "chart", "team",
}


def _error(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _is_finite_pair(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item)
                for item in value)
    )


def _check_id(value: Any, path: str, kind: str) -> list[dict[str, str]]:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        return [_error("invalid_id", path, f"{kind} deve usar slug ASCII de até 64 caracteres")]
    return []


def _check_label(value: Any, path: str, field: str) -> list[dict[str, str]]:
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        return [_error("invalid_label", path, f"{field} deve ter de 1 a 160 caracteres")]
    return []


def validate_flow(flow: Any) -> list[dict[str, str]]:
    """Return structured validation errors without mutating the input document."""
    errors: list[dict[str, str]] = []
    if not isinstance(flow, dict):
        return [_error("invalid_document", "$", "documento deve ser um objeto JSON")]
    if "title" in flow and (not isinstance(flow["title"], str) or not flow["title"].strip() or len(flow["title"]) > 200):
        errors.append(_error("invalid_title", "title", "title deve ter de 1 a 200 caracteres"))

    layout = flow.get("layout", "flow")
    if not isinstance(layout, str) or layout not in LAYOUTS:
        errors.append(_error("invalid_enum", "layout", "layout desconhecido"))
    raw_direction = flow.get("direction", "LR")
    direction = raw_direction.upper() if isinstance(raw_direction, str) else None
    if direction not in DIRECTIONS:
        errors.append(_error("invalid_enum", "direction", "direction deve ser LR ou TB"))
    accent = flow.get("accent")
    if accent is not None and (not isinstance(accent, str) or not COLOR_RE.fullmatch(accent)):
        errors.append(_error("invalid_color", "accent", "accent deve estar no formato #RRGGBB"))

    animation = flow.get("animation", {})
    if not isinstance(animation, dict):
        errors.append(_error("invalid_object", "animation", "animation deve ser um objeto"))
    elif not isinstance(animation.get("mode", "packet"), str) or animation.get("mode", "packet") not in ANIMATION_MODES:
        errors.append(_error("invalid_enum", "animation.mode", "modo de animação desconhecido"))
    elif "speed" in animation and (
        not isinstance(animation["speed"], (int, float))
        or isinstance(animation["speed"], bool)
        or not math.isfinite(animation["speed"])
        or animation["speed"] <= 0
    ):
        errors.append(_error("invalid_number", "animation.speed", "speed deve ser número finito positivo"))

    groups = flow.get("groups", [])
    nodes = flow.get("nodes", [])
    edges = flow.get("edges", [])
    for name, value in (("groups", groups), ("nodes", nodes), ("edges", edges)):
        if not isinstance(value, list):
            errors.append(_error("invalid_array", name, f"{name} deve ser uma lista"))
    if not all(isinstance(value, list) for value in (groups, nodes, edges)):
        return errors

    group_ids: set[str] = set()
    for index, group in enumerate(groups):
        path = f"groups[{index}]"
        if not isinstance(group, dict):
            errors.append(_error("invalid_object", path, "grupo deve ser um objeto"))
            continue
        gid = group.get("id")
        errors.extend(_check_id(gid, f"{path}.id", "id do grupo"))
        if isinstance(gid, str):
            if gid in group_ids:
                errors.append(_error("duplicate_id", f"{path}.id", "id de grupo duplicado"))
            group_ids.add(gid)
        errors.extend(_check_label(group.get("label", gid), f"{path}.label", "label do grupo"))
        if "color" in group and (not isinstance(group["color"], str) or not COLOR_RE.fullmatch(group["color"])):
            errors.append(_error("invalid_color", f"{path}.color", "cor deve estar no formato #RRGGBB"))

    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        path = f"nodes[{index}]"
        if not isinstance(node, dict):
            errors.append(_error("invalid_object", path, "nó deve ser um objeto"))
            continue
        nid = node.get("id")
        errors.extend(_check_id(nid, f"{path}.id", "id do nó"))
        if isinstance(nid, str):
            if nid in node_ids:
                errors.append(_error("duplicate_id", f"{path}.id", "id de nó duplicado"))
            node_ids.add(nid)
        errors.extend(_check_label(node.get("label", nid), f"{path}.label", "label do nó"))
        if "group" in node and (not isinstance(node["group"], str) or node["group"] not in group_ids):
            errors.append(_error("unknown_group", f"{path}.group", "grupo não existe"))
        if "note" in node and (not isinstance(node["note"], str) or len(node["note"]) > 2000):
            errors.append(_error("invalid_note", f"{path}.note", "note deve ter no máximo 2000 caracteres"))
        if "shape" in node and (not isinstance(node["shape"], str) or node["shape"] not in SHAPES):
            errors.append(_error("invalid_enum", f"{path}.shape", "shape desconhecido"))
        if "icon" in node and (not isinstance(node["icon"], str) or node["icon"] not in ICONS):
            errors.append(_error("invalid_enum", f"{path}.icon", "icon desconhecido"))
        if "pos" in node and not _is_finite_pair(node["pos"]):
            errors.append(_error("invalid_position", f"{path}.pos", "pos deve ser um par numérico finito"))

    seen_edges: set[tuple[str, str]] = set()
    for index, edge in enumerate(edges):
        path = f"edges[{index}]"
        if not isinstance(edge, dict):
            errors.append(_error("invalid_object", path, "edge deve ser um objeto"))
            continue
        pair = (edge.get("from"), edge.get("to"))
        endpoints_valid = all(isinstance(value, str) for value in pair)
        if not endpoints_valid or pair[0] not in node_ids or pair[1] not in node_ids:
            errors.append(_error("unknown_edge_endpoint", path, "from e to devem referenciar nós existentes"))
        if endpoints_valid and pair in seen_edges:
            errors.append(_error("duplicate_edge", path, "edge duplicada"))
        if endpoints_valid:
            seen_edges.add(pair)
        if "label" in edge and (not isinstance(edge["label"], str) or len(edge["label"]) > 160):
            errors.append(_error("invalid_label", f"{path}.label", "label da edge deve ter no máximo 160 caracteres"))
        if "animated" in edge and not isinstance(edge["animated"], bool):
            errors.append(_error("invalid_boolean", f"{path}.animated", "animated deve ser booleano"))
        if not isinstance(edge.get("style", "solid"), str) or edge.get("style", "solid") not in STYLES:
            errors.append(_error("invalid_enum", f"{path}.style", "style desconhecido"))
        for side in ("fromSide", "toSide"):
            if side in edge and (not isinstance(edge[side], str) or edge[side] not in SIDES):
                errors.append(_error("invalid_enum", f"{path}.{side}", f"{side} desconhecido"))
        if "dir" in edge and (not isinstance(edge["dir"], str) or edge["dir"] not in {"->", "-", "<->"}):
            errors.append(_error("invalid_enum", f"{path}.dir", "dir desconhecido"))

    return errors


def assert_valid_flow(flow: Any) -> None:
    errors = validate_flow(flow)
    if errors:
        detail = "; ".join(f"{error['path']}: {error['message']}" for error in errors)
        raise ValueError(f"flow.json inválido: {detail}")
