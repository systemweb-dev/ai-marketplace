#!/usr/bin/env python3
"""
Renderiza um diagrama de fluxo/arquitetura a partir de um flow.json -> HTML standalone.

Uso:
  python3 build_flow.py --dir ./flows/<slug>     # le <dir>/flow.json, escreve <dir>/flow.html

flow.json (fonte da verdade):
{
  "title": "Fluxo de request",
  "layout": "flow | tiers | graph",   // flow/graph = camadas E->D; tiers = faixas por grupo
  "direction": "LR | TB",             // LR=esquerda->direita (padrao); TB=cima->baixo (flow/graph)
  "accent": "#2f6bf0",
  "animation": { "mode": "packet | highlight | draw | none", "speed": 1 },
  "groups": [ {"id":"edge","label":"Edge","color":"#..."} ],
  "nodes":  [ {"id":"req","label":"Request HTTP","icon":"user","group":"edge","note":"..."} ],
  "edges":  [ {"from":"req","to":"cf","label":"443","animated":true,"dir":"->","style":"solid"} ]
}

Saida: HTML auto-contido com SVG, tema light/dark, accent, toolbar (play/pause, export SVG/PNG,
tema), animacao e live-reload. Layout determinístico (camadas/faixas) — sem dependencia externa.
"""
import argparse
import html
import json
import os
import shutil
import sys
from collections import defaultdict

from flow_contract import assert_valid_flow

NODE_W, NODE_H = 168, 66
GAPX, GAPY = 88, 34
VGAP = 72       # espaço entre camadas no layout vertical (TB)
MARGIN = 60
LANE_PAD = 26  # respiro vertical extra dentro de cada faixa (tiers)

# ---------------------------------------------------------------- ícones (SVG inline, 24x24, stroke=currentColor)
ICONS = {
    "user": '<circle cx="12" cy="8" r="3.4"/><path d="M5.5 19a6.5 6.5 0 0 1 13 0"/>',
    "server": '<rect x="4" y="4" width="16" height="7" rx="1.5"/><rect x="4" y="13" width="16" height="7" rx="1.5"/><circle cx="7.5" cy="7.5" r="0.9"/><circle cx="7.5" cy="16.5" r="0.9"/>',
    "database": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
    "storage": '<path d="M4 7h16l-1.4 11.2a2 2 0 0 1-2 1.8H7.4a2 2 0 0 1-2-1.8L4 7z"/><path d="M3 5h18"/>',
    "queue": '<rect x="3" y="6" width="5" height="12" rx="1"/><rect x="9.5" y="6" width="5" height="12" rx="1"/><rect x="16" y="6" width="5" height="12" rx="1"/>',
    "cache": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M13 7l-4 6h3l-1 4 4-6h-3l1-4z"/>',
    "shield": '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z"/>',
    "cloud": '<path d="M7 18a4 4 0 0 1 .5-7.95A5 5 0 0 1 17 9.5a3.5 3.5 0 0 1-.5 8.5H7z"/>',
    "balancer": '<circle cx="6" cy="12" r="2.3"/><circle cx="18" cy="6" r="2.3"/><circle cx="18" cy="12" r="2.3"/><circle cx="18" cy="18" r="2.3"/><path d="M8.3 12H15M8 11l7.7-4M8 13l7.7 4"/>',
    "gateway": '<path d="M4 20V8l8-4 8 4v12"/><path d="M9 20v-6h6v6"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>',
    "service": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"/><circle cx="12" cy="12" r="2.6"/>',
    "document": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
    "message": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 6.5L12 13l8.5-6.5"/>',
    "mobile": '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 18h2"/>',
    "browser": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 8h18M6.5 6.2h.01M9 6.2h.01"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
    "decision": '<path d="M12 3l9 9-9 9-9-9 9-9z"/>',
    "external": '<path d="M14 4h6v6M20 4l-8 8M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6"/>',
    "api": '<path d="M8 5l-5 7 5 7M16 5l5 7-5 7M13 4l-2 16"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.4 2.5 14.6 0 17M12 3.5c-2.5 2.4-2.5 14.6 0 17"/>',
    "proxy": '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M9 9l-2.5 3 2.5 3M15 9l2.5 3-2.5 3"/>',
    "cdn": '<path d="M7 16.5a3.4 3.4 0 0 1 .4-6.8A4.4 4.4 0 0 1 16 8.3a2.9 2.9 0 0 1 .3 6.2"/><circle cx="5.5" cy="20" r="1.2"/><circle cx="12" cy="21" r="1.2"/><circle cx="18.5" cy="20" r="1.2"/><path d="M11 14.5l-4.7 4.3M13 14.5l4.7 4.3M12 15v5"/>',
    "firewall": '<rect x="3" y="4" width="18" height="16" rx="1.5"/><path d="M3 9.3h18M3 14.6h18M9 4v5.3M15 9.3v5.3M9 14.6V20M15 14.6V20"/>',
    "function": '<path d="M15.5 5.5A2.5 2.5 0 0 0 13 8v8a2.5 2.5 0 0 1-2.5 2.5M8.5 12H15"/>',
    "container": '<path d="M3 8l9-5 9 5-9 5-9-5z"/><path d="M3 8v8l9 5 9-5V8M12 13v8"/>',
    "search": '<circle cx="11" cy="11" r="6.2"/><path d="M20 20l-4.6-4.6"/>',
    "monitor": '<path d="M3 13h3.5l2-6 3.5 12 2.5-9 1.5 4H21"/>',
    "box": '<rect x="4" y="4" width="16" height="16" rx="2"/>',
}
DEFAULT_ICON = "box"

# ---------------------------------------------------------------- catálogo de componentes
# Blocos prontos pra montar o fluxo: cada item vira um nó (label + icon) na paleta do canvas
# (duplo-clique no vazio) e é o vocabulário que o modelo usa ao interpretar a descrição.
CATALOG = [
    {"cat": "Cliente", "items": [
        {"label": "Usuário", "icon": "user"},
        {"label": "Navegador", "icon": "browser"},
        {"label": "App Mobile", "icon": "mobile"},
        {"label": "Sistema externo", "icon": "external"},
        {"label": "Parceiro / SaaS", "icon": "external"},
        {"label": "Dispositivo IoT", "icon": "monitor"},
    ]},
    {"cat": "Rede / Edge", "items": [
        {"label": "DNS", "icon": "globe"},
        {"label": "CDN", "icon": "cdn"},
        {"label": "WAF", "icon": "shield"},
        {"label": "Firewall", "icon": "firewall"},
        {"label": "Reverse Proxy", "icon": "proxy"},
        {"label": "Load Balancer", "icon": "balancer"},
        {"label": "API Gateway", "icon": "gateway"},
        {"label": "Ingress Controller", "icon": "gateway"},
        {"label": "Service Mesh", "icon": "service"},
        {"label": "NAT Gateway", "icon": "gateway"},
        {"label": "VPN", "icon": "lock"},
        {"label": "Rate Limiter", "icon": "shield"},
    ]},
    {"cat": "Aplicação", "items": [
        {"label": "App Server", "icon": "server"},
        {"label": "Microserviço", "icon": "service"},
        {"label": "API", "icon": "api"},
        {"label": "Function", "icon": "function"},
        {"label": "Container", "icon": "container"},
        {"label": "Worker", "icon": "gear"},
        {"label": "Auth", "icon": "lock"},
        {"label": "Cron Job", "icon": "clock"},
        {"label": "Webhook", "icon": "api"},
        {"label": "GraphQL", "icon": "api"},
        {"label": "BFF", "icon": "service"},
        {"label": "Feature Flag", "icon": "decision"},
    ]},
    {"cat": "Dados", "items": [
        {"label": "Banco SQL", "icon": "database"},
        {"label": "Cache", "icon": "cache"},
        {"label": "Object Storage", "icon": "storage"},
        {"label": "Busca", "icon": "search"},
        {"label": "Data Warehouse", "icon": "database"},
        {"label": "Data Lake", "icon": "storage"},
        {"label": "Vector Database", "icon": "database"},
        {"label": "Read Replica", "icon": "database"},
        {"label": "Session Store", "icon": "storage"},
    ]},
    {"cat": "Mensageria", "items": [
        {"label": "Fila", "icon": "queue"},
        {"label": "Message Broker", "icon": "message"},
        {"label": "E-mail", "icon": "message"},
        {"label": "Notificação", "icon": "message"},
        {"label": "Dead Letter Queue", "icon": "queue"},
        {"label": "Event Bus", "icon": "message"},
        {"label": "Pub/Sub", "icon": "message"},
        {"label": "SMS", "icon": "message"},
    ]},
    {"cat": "Segurança", "items": [
        {"label": "Identity Provider", "icon": "lock"},
        {"label": "OAuth / OIDC", "icon": "lock"},
        {"label": "Secrets Manager", "icon": "lock"},
        {"label": "KMS", "icon": "shield"},
        {"label": "Antivírus", "icon": "shield"},
        {"label": "Zero Trust", "icon": "shield"},
    ]},
    {"cat": "DevOps / Deploy", "items": [
        {"label": "Git Repository", "icon": "document"},
        {"label": "CI Pipeline", "icon": "gear"},
        {"label": "CD Pipeline", "icon": "gear"},
        {"label": "Artifact Registry", "icon": "storage"},
        {"label": "Kubernetes", "icon": "container"},
        {"label": "Serverless", "icon": "function"},
    ]},
    {"cat": "Integrações", "items": [
        {"label": "Stripe", "icon": "external"},
        {"label": "CRM", "icon": "external"},
        {"label": "ERP", "icon": "external"},
        {"label": "Analytics", "icon": "monitor"},
        {"label": "Maps API", "icon": "globe"},
        {"label": "Payment Gateway", "icon": "gateway"},
    ]},
    {"cat": "Observabilidade / Fluxo", "items": [
        {"label": "Monitoring", "icon": "monitor"},
        {"label": "Logs", "icon": "document"},
        {"label": "Scheduler", "icon": "clock"},
        {"label": "Decisão", "icon": "decision"},
        {"label": "Tracing", "icon": "monitor"},
        {"label": "Alertas", "icon": "shield"},
        {"label": "Dashboard", "icon": "monitor"},
        {"label": "Auditoria", "icon": "document"},
    ]},
]


# ---------------------------------------------------------------- layout
def _forward_edges(node_ids, edges):
    """Exclui back-edges (detectadas por DFS) — assim ciclos não inflam as camadas."""
    ids = set(node_ids)
    succ = defaultdict(list)
    for e in edges:
        a, b = e.get("from"), e.get("to")
        if a in ids and b in ids:
            succ[a].append((b, e))
    color = {n: 0 for n in node_ids}  # 0=branco 1=cinza 2=preto
    back = set()
    stack = []
    for root in node_ids:
        if color[root] != 0:
            continue
        stack.append((root, iter(succ[root])))
        color[root] = 1
        while stack:
            u, it = stack[-1]
            advanced = False
            for v, _e in it:
                if color[v] == 1:
                    back.add(id(_e))           # aresta pra ancestral = back-edge
                elif color[v] == 0:
                    color[v] = 1
                    stack.append((v, iter(succ[v])))
                    advanced = True
                    break
            if not advanced:
                color[u] = 2
                stack.pop()
    return [e for e in edges if id(e) not in back]


def _layers(node_ids, edges):
    """Camada (coluna) por caminho mais longo, ignorando back-edges (sem inflar ciclos)."""
    fwd = _forward_edges(node_ids, edges)
    layer = {n: 0 for n in node_ids}
    for _ in range(len(node_ids) + 1):
        changed = False
        for e in fwd:
            a, b = e.get("from"), e.get("to")
            if a in layer and b in layer and layer[b] < layer[a] + 1:
                layer[b] = layer[a] + 1
                changed = True
        if not changed:
            break
    return layer


def layout_layered(node_ids, edges, vertical=False):
    """LR: camada=coluna (x), membros empilham em y. TB: camada=linha (y), membros espalham em x."""
    layer = _layers(node_ids, edges)
    cols = defaultdict(list)
    for n in node_ids:
        cols[layer[n]].append(n)
    nlayers = (max(layer.values()) + 1) if layer else 1
    pos = {}
    if not vertical:
        maxrows = max((len(c) for c in cols.values()), default=1)
        total_h = maxrows * (NODE_H + GAPY) - GAPY
        for L, members in cols.items():
            col_h = len(members) * (NODE_H + GAPY) - GAPY
            y0 = MARGIN + (total_h - col_h) / 2
            for i, n in enumerate(members):
                x = MARGIN + L * (NODE_W + GAPX)
                pos[n] = (x, y0 + i * (NODE_H + GAPY))
        w = MARGIN * 2 + nlayers * (NODE_W + GAPX) - GAPX
        h = MARGIN * 2 + total_h
    else:
        maxcols = max((len(c) for c in cols.values()), default=1)
        total_w = maxcols * (NODE_W + GAPX) - GAPX
        for L, members in cols.items():
            row_w = len(members) * (NODE_W + GAPX) - GAPX
            x0 = MARGIN + (total_w - row_w) / 2
            for i, n in enumerate(members):
                y = MARGIN + L * (NODE_H + VGAP)
                pos[n] = (x0 + i * (NODE_W + GAPX), y)
        w = MARGIN * 2 + total_w
        h = MARGIN * 2 + nlayers * (NODE_H + VGAP) - VGAP
    return pos, w, h, None


def layout_tiers(node_ids, edges, nodes_by_id, groups):
    layer = _layers(node_ids, edges)
    # ordem das faixas: ordem de groups; nós sem grupo vão pra faixa "_" no fim
    order = [g["id"] for g in groups] if groups else []
    seen = list(order)
    for n in node_ids:
        g = nodes_by_id[n].get("group") or "_"
        if g not in seen:
            seen.append(g)
    lane_index = {g: i for i, g in enumerate(seen)}
    lane_h = NODE_H + 2 * LANE_PAD
    pos = {}
    ncols = (max(layer.values()) + 1) if layer else 1
    for n in node_ids:
        g = nodes_by_id[n].get("group") or "_"
        x = MARGIN + layer[n] * (NODE_W + GAPX)
        y = MARGIN + lane_index[g] * lane_h + LANE_PAD
        pos[n] = (x, y)
    w = MARGIN * 2 + ncols * (NODE_W + GAPX) - GAPX
    h = MARGIN * 2 + len(seen) * lane_h
    lanes = [(g, MARGIN + lane_index[g] * lane_h, lane_h) for g in seen if g != "_"]
    return pos, w, h, lanes


# ---------------------------------------------------------------- svg helpers
def _edge_path(x1, y1, x2, y2, vertical=False):
    """Bezier no sentido do layout; faz loop lateral/abaixo quando é aresta de volta."""
    if not vertical:
        if x2 >= x1:
            cx = (x2 - x1) * 0.5
            return f"M{x1:.1f},{y1:.1f} C{x1+cx:.1f},{y1:.1f} {x2-cx:.1f},{y2:.1f} {x2:.1f},{y2:.1f}"
        dy = 70
        return (f"M{x1:.1f},{y1:.1f} C{x1+60:.1f},{y1+dy:.1f} {x2-60:.1f},{y2+dy:.1f} {x2:.1f},{y2:.1f}")
    if y2 >= y1:
        cy = (y2 - y1) * 0.5
        return f"M{x1:.1f},{y1:.1f} C{x1:.1f},{y1+cy:.1f} {x2:.1f},{y2-cy:.1f} {x2:.1f},{y2:.1f}"
    dx = 70
    return (f"M{x1:.1f},{y1:.1f} C{x1+dx:.1f},{y1+60:.1f} {x2+dx:.1f},{y2-60:.1f} {x2:.1f},{y2:.1f}")


def _node_svg(n, x, y, accent):
    icon = ICONS.get(n.get("icon", ""), "")
    label = html.escape(n.get("label", n.get("id", "")))
    has_note = bool(n.get("note"))
    icon_g = (f'<g transform="translate(14,{NODE_H/2-11})" class="ico">'
              f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{icon}</svg></g>') if icon else ""
    tx = 44 if icon else 16
    note_attr = f' data-note="{html.escape(n.get("note",""))}"' if has_note else ""
    dot = f'<circle cx="{NODE_W-12}" cy="12" r="3" class="noteDot"/>' if has_note else ""
    return (f'<g class="node" data-id="{html.escape(n.get("id",""))}" transform="translate({x:.1f},{y:.1f})"{note_attr}>'
            f'<rect x="0" y="0" width="{NODE_W}" height="{NODE_H}" rx="13" class="nbox"/>'
            f'{icon_g}{dot}'
            f'<text x="{tx}" y="{NODE_H/2+4.5}" class="nlabel">{label}</text></g>')


def build(d):
    with open(os.path.join(d, "flow.json"), encoding="utf-8") as f:
        flow = json.load(f)
    assert_valid_flow(flow)

    nodes = flow.get("nodes", [])
    edges = flow.get("edges", [])
    groups = flow.get("groups", [])
    nodes_by_id = {n["id"]: n for n in nodes}
    node_ids = [n["id"] for n in nodes]
    layout = flow.get("layout", "flow")
    direction = (flow.get("direction") or "LR").upper()
    vertical = direction == "TB" and layout != "tiers"
    accent = flow.get("accent", "#2f6bf0")
    anim = (flow.get("animation") or {}).get("mode", "packet")
    speed = float((flow.get("animation") or {}).get("speed", 1) or 1)
    dur = max(0.6, 2.2 / speed)

    if layout == "tiers":
        pos, W, H, lanes = layout_tiers(node_ids, edges, nodes_by_id, groups)
    else:  # flow ou graph -> layout em camadas (horizontal LR ou vertical TB)
        pos, W, H, lanes = layout_layered(node_ids, edges, vertical)

    # override por posição manual (arrasta-e-solta): nós com "pos":[x,y] ficam pinados
    for n in nodes:
        p = n.get("pos")
        if n.get("id") in pos and isinstance(p, (list, tuple)) and len(p) == 2:
            try:
                pos[n["id"]] = (float(p[0]), float(p[1]))
            except (TypeError, ValueError):
                raise ValueError(f"posição inválida para o nó {n['id']}")
    if pos:
        W = max(W, max(x for x, _ in pos.values()) + NODE_W + MARGIN)
        H = max(H, max(y for _, y in pos.values()) + NODE_H + MARGIN)

    # --- grupos (caixas) no modo flow/graph
    group_svg = []
    if layout != "tiers" and groups:
        gcolor = {g["id"]: g.get("color", accent) for g in groups}
        glabel = {g["id"]: g.get("label", g["id"]) for g in groups}
        boxes = defaultdict(lambda: [1e9, 1e9, -1e9, -1e9])
        for n in node_ids:
            g = nodes_by_id[n].get("group")
            if not g:
                continue
            x, y = pos[n]
            b = boxes[g]
            b[0], b[1] = min(b[0], x), min(b[1], y)
            b[2], b[3] = max(b[2], x + NODE_W), max(b[3], y + NODE_H)
        for g, (x0, y0, x1, y1) in boxes.items():
            p = 16
            group_svg.append(
                f'<g class="group"><rect x="{x0-p}" y="{y0-p-14}" width="{x1-x0+2*p}" '
                f'height="{y1-y0+2*p+14}" rx="16" class="gbox" style="--gc:{gcolor.get(g,accent)}"/>'
                f'<text x="{x0-p+6}" y="{y0-p-2}" class="glabel" style="--gc:{gcolor.get(g,accent)}">'
                f'{html.escape(glabel.get(g,g))}</text></g>')

    # --- faixas (tiers)
    if layout == "tiers" and lanes:
        glabel = {g["id"]: g.get("label", g["id"]) for g in groups}
        gcolor = {g["id"]: g.get("color", accent) for g in groups}
        for g, ly, lh in lanes:
            group_svg.append(
                f'<g class="lane"><rect x="{MARGIN-20}" y="{ly}" width="{W-2*(MARGIN-20)}" height="{lh}" '
                f'rx="14" class="lbox" style="--gc:{gcolor.get(g,accent)}"/>'
                f'<text x="{MARGIN-8}" y="{ly+18}" class="glabel" style="--gc:{gcolor.get(g,accent)}">'
                f'{html.escape(glabel.get(g,g))}</text></g>')

    # --- arestas
    edge_svg = []
    for i, e in enumerate(edges):
        a, b = e.get("from"), e.get("to")
        if a not in pos or b not in pos:
            continue
        ax, ay = pos[a]; bx, by = pos[b]
        if vertical:
            x1, y1 = ax + NODE_W / 2, ay + NODE_H
            x2, y2 = bx + NODE_W / 2, by
        else:
            x1, y1 = ax + NODE_W, ay + NODE_H / 2
            x2, y2 = bx, by + NODE_H / 2
        path = _edge_path(x1, y1, x2, y2, vertical)
        cls = "edge" + (" animated" if e.get("animated", True) else "")
        if e.get("style") == "dashed":
            cls += " dashed"
        pid = f"e{i}"
        edge_svg.append(f'<path id="{pid}" data-from="{html.escape(a)}" data-to="{html.escape(b)}" d="{path}" class="{cls}" marker-end="url(#arrow)"/>')
        if e.get("label"):
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 8
            edge_svg.append(f'<text data-from="{html.escape(a)}" data-to="{html.escape(b)}" x="{mx:.0f}" y="{my:.0f}" class="elabel">{html.escape(e["label"])}</text>')
        # bolinha viajando (packet)
        if anim == "packet" and e.get("animated", True):
            edge_svg.append(
                f'<circle r="4.5" class="packet"><animateMotion dur="{dur}s" begin="{i*0.25:.2f}s" '
                f'repeatCount="indefinite"><mpath href="#{pid}"/></animateMotion></circle>')

    node_svg = []
    for idx, n in enumerate(nodes):
        if n.get("id") not in pos:
            continue
        x, y = pos[n["id"]]
        g = _node_svg(n, x, y, accent)
        if anim == "highlight":
            g = g.replace('class="node"', f'class="node hl" style="--d:{idx*0.3:.2f}s"', 1)
        node_svg.append(g)

    title = html.escape(flow.get("title", "Fluxo"))
    page = TEMPLATE
    repl = {
        "%%TITLE%%": title, "%%ACCENT%%": accent, "%%W%%": f"{W:.0f}", "%%H%%": f"{H:.0f}",
        "%%ANIM%%": anim, "%%DUR%%": f"{dur}",
        "%%GROUPS%%": "\n".join(group_svg),
        "%%EDGES%%": "\n".join(edge_svg),
        "%%NODES%%": "\n".join(node_svg),
        "%%FLOWJSON%%": json.dumps(flow, ensure_ascii=False),
        "%%ICONSVG%%": json.dumps(ICONS),
        "%%CATALOG%%": json.dumps(CATALOG, ensure_ascii=False),
        "%%ANIMJS%%": json.dumps(anim),
        "%%POS%%": json.dumps({k: [round(v[0], 1), round(v[1], 1)] for k, v in pos.items()}),
        "%%NW%%": str(NODE_W), "%%NH%%": str(NODE_H),
        "%%EDITORJS%%": editor_js(),
    }
    for k, v in repl.items():
        page = page.replace(k, v)
    out = os.path.join(d, "flow.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(out)


def editor_js() -> str:
    """Concatena os módulos do editor em ordem.

    Ficam embutidos no HTML (e não como <script src>) por dois motivos: o flow.html
    passa a ser um arquivo único que dá pra mandar por e-mail, e módulos ES não
    carregam via file:// por causa de CORS — o que quebraria o diagrama aberto
    direto do disco.
    """
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "editor")
    if not os.path.isdir(base):
        return ""
    partes = []
    for nome in sorted(os.listdir(base)):
        if nome.endswith(".js"):
            with open(os.path.join(base, nome), encoding="utf-8") as f:
                partes.append("/* === %s === */\n%s" % (nome, f.read()))
    # um IIFE só: os módulos compartilham escopo léxico sem virar global
    return "(function(){\n'use strict';\n" + "\n".join(partes) + "\n})();"


TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%%TITLE%% — Flow</title>
<script>(function(){try{if(localStorage.getItem('flow-theme')==='dark')document.documentElement.dataset.theme='dark';}catch(e){}})();</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#f6f8fc;--bg2:#eef2f9;--surface:#ffffff;--ink:#16203a;--muted:#7c879c;
    --line:#e3e9f3;--accent:%%ACCENT%%;--accent-dk:color-mix(in oklab,var(--accent),#000 24%);
    --accent-lt:color-mix(in oklab,var(--accent),#fff 18%);--node:#ffffff;--node-line:#dbe3f1;
    --edge:#9fb0cf;--display:'Hanken Grotesk',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;
  }
  html[data-theme="dark"]{
    --bg:#0c1322;--bg2:#0a1020;--surface:#141d30;--ink:#e8eef9;--muted:#8392ab;
    --line:#243049;--node:#16213a;--node-line:#2a3a59;--edge:#46577a;
    --accent:color-mix(in oklab,%%ACCENT%%,#fff 18%);
    --accent-dk:color-mix(in oklab,var(--accent),#fff 30%);--accent-lt:color-mix(in oklab,var(--accent),#fff 12%);
  }
  *{box-sizing:border-box;} body{margin:0;background:radial-gradient(1100px 600px at 80% -10%,color-mix(in oklab,var(--accent),transparent 90%),transparent 60%),linear-gradient(180deg,var(--bg),var(--bg2));color:var(--ink);font-family:var(--display);height:100vh;overflow:hidden;display:flex;flex-direction:column;}
  .bar{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:12px;padding:12px 20px;backdrop-filter:blur(10px);background:color-mix(in oklab,var(--bg),transparent 25%);border-bottom:1px solid var(--line);}
  .bar h1{font-size:16px;margin:0;font-weight:700;letter-spacing:-.01em;}
  .bar .sp{flex:1;}
  .ed-hint{font:500 10.5px/1.3 var(--mono);color:var(--muted);max-width:430px;}
  @media(max-width:900px){.ed-hint{display:none;}}
  /* foco visível em tudo que recebe teclado: sem isso, navegar por Tab é andar no escuro */
  .bar button:focus-visible,.fpanel button:focus-visible,.fdock button:focus-visible,
  .fpanel input:focus-visible,.fpanel select:focus-visible,.fpanel textarea:focus-visible,
  .fdock input:focus-visible,.diagram .node:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
  /* o que só o leitor de tela precisa ouvir (erro de validação, resultado de uma ação) */
  .btn.primary.sujo::after{content:'';width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block;margin-left:6px;vertical-align:middle;}
  .sr{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0;}
  /* telas estreitas: paleta e painel viram gavetas sobre o canvas, que continua utilizável */
  @media(max-width:900px){
    .fdock{position:fixed;z-index:24;top:52px;bottom:0;left:0;width:min(78vw,300px);box-shadow:0 10px 40px -12px rgba(10,20,50,.35);}
    .fdock.closed{transform:translateX(-100%);}
    .fpanel{position:fixed;z-index:25;top:52px;bottom:0;right:0;width:min(84vw,320px);box-shadow:0 10px 40px -12px rgba(10,20,50,.35);}
    .stage{margin:0;}
  }
  @media(max-width:640px){
    .bar h1{max-width:9rem;}
    /* um de cada vez: com os dois abertos não sobra canvas nenhum */
    body.painel-aberto .fdock{transform:translateX(-100%);}
  }
  .btn{font:600 12px/1 var(--mono);letter-spacing:.04em;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:8px 12px;cursor:pointer;transition:.15s;}
  .btn:hover{border-color:var(--accent);color:var(--accent-dk);}
  .btn.primary{color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent-dk));border:0;}
  .stage{flex:1;min-height:0;overflow:auto;padding:0;}
  svg.diagram{display:block;}
  .gbox{fill:color-mix(in oklab,var(--gc),transparent 92%);stroke:color-mix(in oklab,var(--gc),transparent 60%);stroke-width:1.5;stroke-dasharray:5 5;}
  .lbox{fill:color-mix(in oklab,var(--gc),transparent 94%);stroke:color-mix(in oklab,var(--gc),transparent 70%);stroke-width:1.4;}
  .glabel{fill:color-mix(in oklab,var(--gc),#000 10%);font:700 11px/1 var(--mono);letter-spacing:.12em;text-transform:uppercase;}
  html[data-theme="dark"] .glabel{fill:color-mix(in oklab,var(--gc),#fff 25%);}
  .nbox{fill:var(--node);stroke:var(--node-line);stroke-width:1.5;filter:drop-shadow(0 10px 18px rgba(20,30,60,.10));}
  .node .ico{color:var(--accent-dk);}
  .nlabel{fill:var(--ink);font:600 13px/1 var(--display);}
  .noteDot{fill:var(--accent);}
  .node.hl .nbox{animation:pulse 3s ease-in-out infinite;animation-delay:var(--d);}
  @keyframes pulse{0%,72%,100%{stroke:var(--node-line);}80%{stroke:var(--accent);filter:drop-shadow(0 0 10px var(--accent));}}
  .edge{fill:none;stroke:var(--edge);stroke-width:2;}
  .edge.dashed{stroke-dasharray:6 5;}
  .edge.animated{stroke-dasharray:7 6;animation:flow %%DUR%%s linear infinite;}
  @keyframes flow{to{stroke-dashoffset:-26;}}
  .packet{fill:var(--accent);filter:drop-shadow(0 0 5px var(--accent));}
  .elabel{fill:var(--muted);font:600 11px/1 var(--mono);text-anchor:middle;}
  #arrow path{fill:var(--edge);}
  body.paused .edge.animated{animation:none;} body.paused .packet{display:none;} body.paused .node.hl .nbox{animation:none;}
  body.export{height:auto;overflow:visible;} body.export .bar{display:none!important;} body.export .stage{overflow:visible;}
  .tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--bg);font-size:12px;padding:7px 10px;border-radius:8px;max-width:260px;opacity:0;transition:.12s;z-index:9;}
  svg .node{cursor:grab;} body.dragging,body.dragging *{cursor:grabbing!important;} body.dragging .tip{opacity:0!important;}
  .stage{cursor:grab;} body.panning,body.panning *{cursor:grabbing!important;} body.panning .tip{opacity:0!important;}
  /* editor de canvas */
  .node.sel .nbox{stroke:var(--accent);stroke-width:2.5;}
  .edge.sel{stroke:var(--accent);stroke-width:3;}
  .edge.ghost{stroke:var(--accent);stroke-dasharray:4 4;opacity:.7;pointer-events:none;}
  .port{fill:var(--accent);stroke:var(--surface);stroke-width:1.5;opacity:0;cursor:crosshair;transition:opacity .12s;}
  .node:hover .port,.node.sel .port{opacity:.95;}
  .ehandle{fill:var(--surface);stroke:var(--accent);stroke-width:2.5;cursor:grab;}
  .ntb{position:fixed;display:none;gap:5px;z-index:20;}
  .ntb button{font-size:14px;line-height:1;width:28px;height:28px;border:1px solid var(--line);background:var(--surface);border-radius:7px;cursor:pointer;box-shadow:0 6px 18px -8px rgba(10,20,50,.4);}
  .ntb button:hover{border-color:var(--accent);}
  .ipal{position:fixed;z-index:21;background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:7px;display:grid;grid-template-columns:repeat(6,1fr);gap:3px;box-shadow:0 16px 50px -16px rgba(10,20,50,.45);max-width:236px;}
  .ipal button{width:30px;height:30px;display:flex;align-items:center;justify-content:center;color:var(--ink);background:var(--bg);border:1px solid transparent;border-radius:7px;cursor:pointer;}
  .ipal button:hover{border-color:var(--accent);color:var(--accent-dk);}
  .inlED{position:fixed;z-index:22;font:600 13px var(--display);text-align:center;border:2px solid var(--accent);border-radius:7px;padding:3px 6px;background:var(--surface);color:var(--ink);outline:none;box-shadow:0 8px 24px -10px rgba(10,20,50,.4);}
  /* paleta de componentes (catálogo) */
  .cpal{position:fixed;z-index:23;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:10px;box-shadow:0 20px 60px -18px rgba(10,20,50,.5);width:302px;max-height:66vh;overflow:auto;}
  .cpal .srch{width:100%;margin-bottom:8px;font:500 12px var(--display);padding:7px 9px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);outline:none;}
  .cpal .srch:focus{border-color:var(--accent);}
  .cpal h4{margin:9px 4px 4px;font:700 10px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);}
  .cpal h4:first-child{margin-top:0;}
  .cpal .grid{display:grid;grid-template-columns:1fr 1fr;gap:4px;}
  .cpal button{display:flex;align-items:center;gap:7px;padding:7px 8px;font:600 12px var(--display);color:var(--ink);background:var(--bg);border:1px solid transparent;border-radius:8px;cursor:pointer;text-align:left;overflow:hidden;}
  .cpal button span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .cpal button:hover{border-color:var(--accent);color:var(--accent-dk);}
  .cpal button svg{flex:none;color:var(--accent-dk);}
  .cpal .blank{grid-column:1/-1;justify-content:center;color:var(--muted);}
  /* menu de grupos (atribuir/criar) */
  .gmenu{position:fixed;z-index:23;background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:6px;min-width:176px;box-shadow:0 16px 50px -16px rgba(10,20,50,.45);}
  .gmenu button{display:flex;align-items:center;gap:8px;width:100%;text-align:left;padding:7px 9px;font:600 12px var(--display);color:var(--ink);background:none;border:0;border-radius:7px;cursor:pointer;}
  .gmenu button:hover{background:var(--bg);}
  .gmenu .dot{width:11px;height:11px;border-radius:3px;flex:none;}
  .gmenu .sep{height:1px;background:var(--line);margin:4px 2px;}
  .gmenu input{width:100%;font:500 12px var(--display);padding:6px 8px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--ink);outline:none;margin-top:3px;}
  .gmenu input:focus{border-color:var(--accent);}

  /* ---------- toolbar: botões de ícone agrupados ---------- */
  .grp{display:flex;gap:2px;padding:2px;background:var(--soft,rgba(127,127,127,.09));border-radius:9px;}
  .ib{width:29px;height:29px;display:grid;place-items:center;border:0;background:transparent;color:var(--ink);
      border-radius:7px;cursor:pointer;font:600 15px/1 var(--display);transition:background .12s;}
  .ib:hover:not(:disabled){background:var(--bg);}
  .ib:disabled{opacity:.3;cursor:default;}

  /* ---------- painel de propriedades ---------- */
  .fpanel{position:fixed;top:56px;right:0;bottom:0;width:288px;background:var(--card,var(--bg));
          border-left:1px solid var(--line);padding:16px;overflow-y:auto;z-index:40;
          transform:translateX(100%);transition:transform .18s ease;display:flex;flex-direction:column;gap:13px;}
  .fpanel.open{transform:none;}
  body.presenting .fpanel,body.export .fpanel{display:none;}
  .ph{display:flex;flex-direction:column;gap:2px;padding-bottom:11px;border-bottom:1px solid var(--line);}
  .ph b{font:700 13px var(--display);}
  .ph span{font:500 10.5px var(--mono);color:var(--muted);}
  .fld{display:flex;flex-direction:column;gap:5px;}
  .fl{font:700 9.5px/1 var(--mono);letter-spacing:.09em;text-transform:uppercase;color:var(--muted);}
  .finp,.fsel,.fta{width:100%;font:500 12.5px var(--display);padding:7px 9px;border:1px solid var(--line);
                   border-radius:8px;background:var(--bg);color:var(--ink);outline:none;}
  .fta{min-height:62px;resize:vertical;line-height:1.5;}
  .finp:focus,.fsel:focus,.fta:focus{border-color:var(--accent);}
  .fico{display:grid;grid-template-columns:repeat(7,1fr);gap:3px;}
  .fico button{aspect-ratio:1;display:grid;place-items:center;border:1px solid transparent;border-radius:7px;
               background:var(--bg);color:var(--ink);cursor:pointer;}
  .fico button:hover{border-color:var(--line);}
  .fico button.on{border-color:var(--accent);color:var(--accent);background:var(--accent-soft,transparent);}
  .fchk{display:flex;align-items:center;gap:8px;font:500 12px var(--display);color:var(--ink);cursor:pointer;}
  .frow{display:flex;gap:7px;margin-top:auto;padding-top:11px;}
  .fbtn{flex:1;font:600 12px var(--display);padding:8px;border:1px solid var(--line);border-radius:8px;
        background:var(--bg);color:var(--ink);cursor:pointer;}
  .fbtn:hover{border-color:var(--accent);}
  .fbtn.danger:hover{border-color:#d3453b;color:#d3453b;}

  /* ---------- guias de alinhamento e laço ---------- */
  .guide{stroke:#e0407f;stroke-width:1;stroke-dasharray:4 4;opacity:.85;pointer-events:none;}
  .marquee{fill:var(--accent);fill-opacity:.08;stroke:var(--accent);stroke-width:1;stroke-dasharray:4 3;}

  /* ---------- grupo recolhido ---------- */
  .gcollapsed{cursor:pointer;}
  .cbox{fill:var(--gc);fill-opacity:.1;stroke:var(--gc);stroke-width:1.5;}
  .clabel{font:700 14px var(--display);fill:var(--ink);}
  .csub{font:500 10px var(--mono);fill:var(--muted);}
  .cchev{font:700 17px var(--display);fill:var(--muted);}
  .gtoggle{font:700 15px var(--display);fill:var(--gc);cursor:pointer;opacity:.75;}
  .gtoggle:hover{opacity:1;}
  .nstripe{fill:var(--gc);}

  /* ---------- apresentação ---------- */
  .node.dim,.edge.dim,.elabel.dim{opacity:.13;transition:opacity .3s;}
  body.presenting .bar .btn,body.presenting .bar .ib,body.presenting .bar .grp{display:none;}
  .pbar{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);display:flex;align-items:center;gap:11px;
        background:var(--card,var(--bg));border:1px solid var(--line);border-radius:13px;padding:9px 11px;
        box-shadow:0 10px 34px rgba(0,0,0,.19);z-index:60;max-width:min(720px,92vw);}
  .pbar button{width:31px;height:31px;border:0;border-radius:8px;background:var(--bg);color:var(--ink);
               cursor:pointer;font:600 17px/1 var(--display);}
  .pbar button:hover{background:var(--accent);color:#fff;}
  .pbar button.x{width:auto;padding:0 13px;font:600 12px var(--display);}
  .pinfo{display:flex;flex-direction:column;gap:1px;min-width:0;}
  .pinfo b{font:700 11.5px var(--display);}
  .pinfo span{font:500 10.5px var(--mono);color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

  /* ---------- busca ---------- */
  .fsearch{position:fixed;top:76px;left:50%;transform:translateX(-50%);width:min(430px,92vw);z-index:70;
           background:var(--card,var(--bg));border:1px solid var(--line);border-radius:13px;padding:9px;
           box-shadow:0 14px 40px rgba(0,0,0,.2);}
  .fsearch input{width:100%;font:500 13.5px var(--display);padding:9px 11px;border:1px solid var(--line);
                 border-radius:9px;background:var(--bg);color:var(--ink);outline:none;}
  .fsearch input:focus{border-color:var(--accent);}
  .fsearch .res{max-height:290px;overflow-y:auto;margin-top:7px;display:flex;flex-direction:column;gap:2px;}
  .fsearch .res button{display:flex;justify-content:space-between;align-items:center;gap:9px;width:100%;
                       text-align:left;border:0;background:transparent;color:var(--ink);cursor:pointer;
                       padding:7px 10px;border-radius:8px;font:500 12.5px var(--display);}
  .fsearch .res button:hover,.fsearch .res button.on{background:var(--accent);color:#fff;}
  .fsearch .res em{font:500 10px var(--mono);opacity:.65;font-style:normal;}

  /* ---------- paleta fixa (arrastar para o diagrama) ---------- */
  .fdock{position:fixed;top:56px;left:0;bottom:0;width:196px;background:var(--card,var(--bg));
         border-right:1px solid var(--line);display:flex;flex-direction:column;z-index:35;}
  .fdock.closed{width:38px;}
  body.presenting .fdock,body.export .fdock{display:none;}
  .dkh{display:flex;align-items:center;justify-content:space-between;gap:6px;padding:10px 8px 8px 12px;
       font:700 9.5px/1 var(--mono);letter-spacing:.09em;text-transform:uppercase;color:var(--muted);}
  .fdock.closed .dkh span{display:none;}
  .dktog{width:22px;height:22px;border:0;background:transparent;color:var(--muted);cursor:pointer;
         border-radius:6px;font:600 14px/1 var(--display);}
  .dktog:hover{background:var(--bg);color:var(--ink);}
  .dksrch{margin:0 8px 8px;font:500 11.5px var(--display);padding:6px 8px;border:1px solid var(--line);
          border-radius:7px;background:var(--bg);color:var(--ink);outline:none;}
  .dksrch:focus{border-color:var(--accent);}
  .dkbody{flex:1;overflow-y:auto;padding:0 8px 12px;}
  .dksection{display:block;width:100%;margin:8px 0 3px;padding:7px 5px;border:0;border-bottom:1px solid var(--line);
             background:transparent;color:var(--muted);cursor:pointer;text-align:left;font:700 9px var(--mono);
             letter-spacing:.1em;text-transform:uppercase;}
  .dksection:hover{color:var(--accent);}
  .dkbody h5{margin:9px 0 5px 4px;font:700 8.5px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
  .dkgrid{display:flex;flex-direction:column;gap:2px;}
  /* formas em duas colunas: são 21 e, em lista, empurravam as categorias para fora da tela */
  .dkgrid.duas{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:3px;}
  .dkgrid[hidden]{display:none;}
  .dkit{display:flex;align-items:center;gap:8px;width:100%;text-align:left;border:1px solid transparent;
        background:transparent;color:var(--ink);cursor:grab;padding:6px 8px;border-radius:7px;
        font:500 11.5px var(--display);}
  .dkit:hover{background:var(--bg);border-color:var(--line);}
  .dkit:active{cursor:grabbing;}
  .dkit span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .dkit .shp{flex:none;fill:none;stroke:currentColor;stroke-width:1.6;opacity:.72;}
  .dkit.dksh{flex-direction:column;align-items:center;gap:4px;text-align:center;padding:7px 4px;}
  .dkit.dksh span{max-width:100%;font-size:10.5px;line-height:1.2;white-space:normal;}
  .dkit:hover .shp{opacity:1;color:var(--accent);}
  .fnote{margin:0;font:500 11px/1.5 var(--display);color:var(--muted);}
  .nlabel.mid{text-anchor:middle;}
  .nedge{stroke:var(--line);stroke-width:1.3;fill:none;}
  /* as 4 portas só aparecem quando são úteis: ao passar sobre o nó ou ao conectar */
  .node .port{opacity:0;transition:opacity .12s;cursor:crosshair;}
  .node:hover .port,.node.sel .port,body.connecting .node .port{opacity:1;}
  body.connecting .node:hover .port{r:7.5;}
  .dkempty{margin:12px 4px;font:500 11px var(--display);color:var(--muted);}
  .dkghost{position:fixed;z-index:90;pointer-events:none;display:flex;align-items:center;gap:7px;
           padding:7px 11px;border-radius:10px;font:600 12px var(--display);
           background:var(--card,var(--bg));border:1px solid var(--line);color:var(--muted);
           box-shadow:0 8px 22px rgba(0,0,0,.17);opacity:.9;}
  .dkghost.ok{border-color:var(--accent);color:var(--accent);}
  /* o canvas encolhe quando as laterais abrem — sem isso os nós ficam DEBAIXO do painel,
     impossíveis de clicar ou de receber uma conexão solta em cima */
  .stage{margin-left:196px;transition:margin .18s ease;}
  body:has(.fpanel.open) .stage{margin-right:288px;}
  body:has(.fdock.closed) .stage{margin-left:38px;}
  body.presenting .stage,body.export .stage{margin-left:0;}
</style>
</head>
<body>
<div class="bar" role="toolbar" aria-label="Ferramentas do diagrama">
  <h1>%%TITLE%%</h1>
  <div class="grp">
    <button class="ib" id="undoBtn" title="Desfazer (Ctrl+Z)" aria-label="Desfazer"><span aria-hidden="true">↶</span></button>
    <button class="ib" id="redoBtn" title="Refazer (Ctrl+Shift+Z)" aria-label="Refazer"><span aria-hidden="true">↷</span></button>
  </div>
  <div class="grp">
    <button class="ib" id="zoomOut" title="Diminuir (−)" aria-label="Diminuir o zoom"><span aria-hidden="true">−</span></button>
    <button class="ib" id="fitBtn" title="Enquadrar (0)" aria-label="Enquadrar o diagrama"><span aria-hidden="true">⊡</span></button>
    <button class="ib" id="zoomIn" title="Aumentar (+)" aria-label="Aumentar o zoom"><span aria-hidden="true">+</span></button>
  </div>
  <button class="ib" id="searchBtn" title="Buscar nó (Ctrl+F)" aria-label="Buscar nó"><span aria-hidden="true">⌕</span></button>
  <div class="sp"></div>
  <button class="btn" id="presentBtn" title="Percorrer o fluxo etapa por etapa" aria-label="Apresentar o fluxo etapa por etapa"><span aria-hidden="true">▶</span> Apresentar</button>
  <button class="btn" id="autoPos" title="Voltar ao layout automático" aria-label="Voltar ao layout automático"><span aria-hidden="true">⤢</span> Auto</button>
  <button class="btn" id="play" aria-label="Pausar a animação do fluxo"><span aria-hidden="true">⏸</span> Pausar</button>
  <button class="btn" onclick="exp('svg')" aria-label="Exportar em SVG">SVG</button>
  <button class="btn" onclick="exp('png')" aria-label="Exportar em PNG">PNG</button>
  <button class="btn" onclick="tg()" aria-label="Alternar tema claro e escuro"><span aria-hidden="true">◑</span> Tema</button>
  <button class="btn primary" id="savePos" title="Salvar no flow.json (Ctrl+S)" aria-label="Salvar no flow.json">Salvar</button>
  <button class="ib" id="helpBtn" title="Atalhos" aria-label="Ver os atalhos de teclado"><span aria-hidden="true">?</span></button>
</div>
<p class="sr" id="anuncio" role="status" aria-live="polite"></p>
<div class="stage">
  <svg class="diagram" id="dg" data-vb="0 0 %%W%% %%H%%" viewBox="0 0 %%W%% %%H%%" width="%%W%%" height="%%H%%" xmlns="http://www.w3.org/2000/svg">
    <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z"/></marker></defs>
    %%GROUPS%%
    %%EDGES%%
    %%NODES%%
  </svg>
</div>
<div class="tip" id="tip"></div>
<script>
  window.FLOW = %%FLOWJSON%%;
  window.POS = %%POS%%;
  window.ICON_SVG = %%ICONSVG%%;
  window.CATALOG = %%CATALOG%%;
  window.ANIM = %%ANIMJS%%;
  window.DUR = %%DUR%%;
  window.NW = %%NW%%; window.NH = %%NH%%;
</script>
<script>%%EDITORJS%%</script>
<script>
  function tg(){const h=document.documentElement;const d=h.dataset.theme==='dark';if(d)h.removeAttribute('data-theme');else h.dataset.theme='dark';try{localStorage.setItem('flow-theme',d?'light':'dark');}catch(e){}}
  const pb=document.getElementById('play');
  pb.onclick=()=>{document.body.classList.toggle('paused');pb.textContent=document.body.classList.contains('paused')?'▶ Tocar':'⏸ Pausar';};
  // tooltips de nota (delegação — sobrevive ao re-render do editor)
  const tip=document.getElementById('tip'), dg=document.getElementById('dg');
  dg.addEventListener('mousemove',e=>{const n=e.target.closest&&e.target.closest('.node[data-note]');
    if(n){tip.textContent=n.getAttribute('data-note');tip.style.opacity=1;tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px';}else tip.style.opacity=0;});
  dg.addEventListener('mouseleave',()=>tip.style.opacity=0);
  // export
  function exp(kind){
    const src=document.getElementById('dg');
    const svg=src.cloneNode(true);
    const vb=src.getAttribute('data-vb'); // exporta justo no conteúdo, não no canvas expandido
    if(vb){const p=vb.split(' ');svg.setAttribute('viewBox',vb);svg.setAttribute('width',p[2]);svg.setAttribute('height',p[3]);}
    svg.querySelectorAll('.port,.ehandle').forEach(e=>e.remove());
    const cs=getComputedStyle(document.body);
    svg.setAttribute('style','background:'+cs.backgroundColor);
    const xml=new XMLSerializer().serializeToString(svg);
    const blob=new Blob([xml],{type:'image/svg+xml'});
    if(kind==='svg'){dl(URL.createObjectURL(blob),'flow.svg');return;}
    const img=new Image();const url=URL.createObjectURL(blob);
    img.onload=()=>{const sc=2,c=document.createElement('canvas');c.width=img.width*sc;c.height=img.height*sc;
      const ctx=c.getContext('2d');ctx.scale(sc,sc);ctx.drawImage(img,0,0);URL.revokeObjectURL(url);
      c.toBlob(b=>dl(URL.createObjectURL(b),'flow.png'));};
    img.src=url;
  }
  function dl(href,name){const a=document.createElement('a');a.href=href;a.download=name;a.click();}
  // live-reload
  let _lm=null;setInterval(async()=>{try{const r=await fetch(location.pathname,{method:'HEAD',cache:'no-store'});
    const lm=r.headers.get('Last-Modified');if(_lm&&lm&&lm!==_lm)location.reload();_lm=lm;}catch(e){}},1500);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="diretorio com flow.json")
    args = ap.parse_args()
    dd = os.path.expanduser(args.dir)
    if not os.path.isfile(os.path.join(dd, "flow.json")):
        sys.exit(f"flow.json nao encontrado em {dd}")
    build(dd)
