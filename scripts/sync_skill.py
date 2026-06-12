#!/usr/bin/env python3
"""Sync de skills locais (~/.claude/skills) -> repositório-marketplace.

Cada skill vira um plugin instalável individualmente no formato oficial do
Claude Code:

    plugins/<skill>/
        .claude-plugin/plugin.json
        skills/<skill>/SKILL.md   (+ subdiretórios da skill)

O script também registra/atualiza a skill no .claude-plugin/marketplace.json e
regenera a tabela de skills do README.md (entre os marcadores SKILLS:START/END).

Uso:
    python3 scripts/sync_skill.py sync <skill> [--from DIR] [--category CAT] [--bump PART] [--dry-run]
    python3 scripts/sync_skill.py import <skill> [--to DIR] [--force] [--dry-run]   # repo -> ~/.claude/skills
    python3 scripts/sync_skill.py remove <skill> [--dry-run]
    python3 scripts/sync_skill.py list
    python3 scripts/sync_skill.py readme        # só regenera a tabela do README

Sem dependências além do PyYAML (já presente). Não faz commit nem push.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ERRO: PyYAML não encontrado. Instale com: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_FILE = ROOT / ".claude-plugin" / "marketplace.json"
README_FILE = ROOT / "README.md"
PLUGINS_DIR = ROOT / "plugins"
DEFAULT_SKILLS_DIR = Path.home() / ".claude" / "skills"
MARKETPLACE_NAME = "ai-marketplace"
OWNER = {"name": "systemweb-dev"}

# Itens que nunca devem ir para o repositório ao copiar uma skill.
RSYNC_EXCLUDES = [
    ".git", ".venv", "venv", "node_modules", "__pycache__", "*.pyc",
    ".pytest_cache", ".DS_Store", "*.swp", "*.swo", "*.log", "*-workspace",
]

# Categoria padrão aplicada a cada skill (sobrescreva por sync com --category).
DEFAULT_CATEGORY = "development"

README_START = "<!-- SKILLS:START -->"
README_END = "<!-- SKILLS:END -->"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def flatten(text: str) -> str:
    """Colapsa qualquer whitespace/quebra de linha em espaços únicos."""
    return " ".join((text or "").split())


# Nome de skill = slug seguro. Bloqueia '/', '..' e absolutos → nenhum path traversal.
SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def validate_name(name: str) -> str:
    if ".." in name or "/" in name or not SAFE_NAME.match(name):
        sys.exit(
            f"ERRO: nome de skill inválido: '{name}'. Use apenas letras minúsculas, "
            f"números, '.', '_' e '-' (sem '/', sem '..')."
        )
    return name


def display(path) -> str:
    """Exibe caminhos com ~ no lugar do home (nunca mostra path pessoal na tela)."""
    p = str(path)
    home = str(Path.home())
    return "~" + p[len(home):] if p == home or p.startswith(home + "/") else p


def short_desc(text: str, limit: int = 160) -> str:
    """Primeira frase (ou recorte) da descrição, para a tabela do README."""
    text = flatten(text)
    for stop in (". ", "? ", "! "):
        idx = text.find(stop)
        if 0 < idx <= limit:
            return text[: idx + 1].strip()
    if len(text) > limit:
        return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def read_frontmatter(skill_md: Path) -> dict:
    """Lê o frontmatter YAML entre os dois primeiros '---' de um SKILL.md."""
    raw = skill_md.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"{skill_md} não começa com frontmatter '---'.")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{skill_md} tem frontmatter malformado.")
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{skill_md}: frontmatter não é um mapa YAML.")
    return data


def load_marketplace() -> dict:
    data = json.loads(MARKETPLACE_FILE.read_text(encoding="utf-8"))
    data.setdefault("plugins", [])
    return data


def save_marketplace(data: dict) -> None:
    data["plugins"].sort(key=lambda p: p["name"])
    MARKETPLACE_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def warn_personal_data(skill_dir: Path) -> list[str]:
    """Heurística leve: avisa sobre caminhos absolutos pessoais vazados."""
    warnings = []
    home = str(Path.home())
    for path in skill_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if home in text:
            rel = path.relative_to(skill_dir)
            warnings.append(f"  ⚠ {rel} contém caminho absoluto do seu diretório home — sanitize antes de publicar")
    return warnings


# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #
def cmd_sync(args) -> None:
    name = validate_name(args.skill)
    src = Path(args.from_dir).expanduser() / name if args.from_dir else DEFAULT_SKILLS_DIR / name
    skill_md = src / "SKILL.md"
    if not skill_md.is_file():
        sys.exit(f"ERRO: SKILL.md não encontrado em {display(src)}")

    fm = read_frontmatter(skill_md)
    fm_name = fm.get("name")
    description = fm.get("description")
    if not description:
        sys.exit(f"ERRO: frontmatter de {name} sem 'description'.")
    if fm_name and fm_name != name:
        print(f"  ⚠ frontmatter name='{fm_name}' difere do diretório '{name}'.")

    for w in warn_personal_data(src):
        print(w)

    category = args.category or DEFAULT_CATEGORY
    plugin_dir = PLUGINS_DIR / name
    plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"
    skill_dest = plugin_dir / "skills" / name

    # Versão: preserva a existente, ou começa em 0.1.0; --bump incrementa.
    version = "0.1.0"
    if plugin_json_path.is_file():
        version = json.loads(plugin_json_path.read_text(encoding="utf-8")).get("version", version)
    if args.bump:
        version = bump_version(version, args.bump)

    print(f"\n→ Sync '{name}'  (categoria: {category}, versão: {version})")
    print(f"  origem: {display(src)}")
    print(f"  destino: {skill_dest.relative_to(ROOT)}")

    if args.dry_run:
        print("  [dry-run] nada foi escrito.")
        return

    plugin_json_path.parent.mkdir(parents=True, exist_ok=True)
    skill_dest.mkdir(parents=True, exist_ok=True)

    # rsync espelha a skill (com --delete) excluindo lixo de build/eval.
    cmd = ["rsync", "-a", "--delete"]
    for pat in RSYNC_EXCLUDES:
        cmd += ["--exclude", pat]
    cmd += [f"{src}/", f"{skill_dest}/"]
    subprocess.run(cmd, check=True)

    plugin_json = {
        "name": name,
        "description": flatten(description),
        "version": version,
        "author": OWNER,
    }
    plugin_json_path.write_text(
        json.dumps(plugin_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    mp = load_marketplace()
    entry = {
        "name": name,
        "source": f"./plugins/{name}",
        "description": flatten(description),
        "category": category,
    }
    mp["plugins"] = [p for p in mp["plugins"] if p["name"] != name] + [entry]
    save_marketplace(mp)
    regenerate_readme(mp)

    print(f"  ✓ plugin.json, marketplace.json e README atualizados.")
    print(f"\nRevise o diff e, quando aprovar, faça commit (Conventional Commits) e push.")


def cmd_import(args) -> None:
    """Traz a skill do repositório de volta para ~/.claude/skills (para editar)."""
    name = validate_name(args.skill)
    src = PLUGINS_DIR / name / "skills" / name
    if not (src / "SKILL.md").is_file():
        sys.exit(
            f"ERRO: skill '{name}' não está publicada no repositório "
            f"({(src / 'SKILL.md').relative_to(ROOT)} ausente)."
        )
    dest_base = Path(args.to_dir).expanduser() if args.to_dir else DEFAULT_SKILLS_DIR
    dest = dest_base / name

    print(f"\n← Import '{name}'  (repositório → local, para edição)")
    print(f"  origem: {src.relative_to(ROOT)}")
    print(f"  destino: {display(dest)}")

    if dest.exists() and not args.force:
        sys.exit(
            f"ERRO: {display(dest)} já existe. Edite direto nele, ou use --force para "
            f"sobrescrever com a versão do repositório (descarta mudanças locais não sincronizadas)."
        )
    if args.dry_run:
        print("  [dry-run] nada foi escrito.")
        return

    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a", "--delete"]
    for pat in RSYNC_EXCLUDES:
        cmd += ["--exclude", pat]
    cmd += [f"{src}/", f"{dest}/"]
    subprocess.run(cmd, check=True)

    print(f"  ✓ skill disponível em {display(dest)} — o Claude Code já a carrega de lá.")
    print(f"\nMelhore a skill e depois publique de volta com:  make sync SKILL={name}")


def cmd_remove(args) -> None:
    name = validate_name(args.skill)
    plugin_dir = PLUGINS_DIR / name
    if args.dry_run:
        print(f"[dry-run] removeria {plugin_dir} e a entrada '{name}' do marketplace.")
        return
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
        print(f"  ✓ removido {plugin_dir}")
    mp = load_marketplace()
    before = len(mp["plugins"])
    mp["plugins"] = [p for p in mp["plugins"] if p["name"] != name]
    save_marketplace(mp)
    regenerate_readme(mp)
    print(f"  ✓ marketplace/README atualizados ({before - len(mp['plugins'])} entrada removida).")


def cmd_list(_args) -> None:
    mp = load_marketplace()
    published = {p["name"] for p in mp["plugins"]}
    print("Skills locais em", display(DEFAULT_SKILLS_DIR) + ":\n")
    if not DEFAULT_SKILLS_DIR.is_dir():
        print("  (diretório não encontrado)")
        return
    for d in sorted(DEFAULT_SKILLS_DIR.iterdir()):
        if not (d / "SKILL.md").is_file():
            continue
        mark = "✓ publicada" if d.name in published else "· não publicada"
        print(f"  {mark:18} {d.name}")


def cmd_readme(_args) -> None:
    regenerate_readme(load_marketplace())
    print("✓ Tabela do README regenerada.")


# --------------------------------------------------------------------------- #
# README + versão
# --------------------------------------------------------------------------- #
def regenerate_readme(mp: dict) -> None:
    plugins = sorted(mp["plugins"], key=lambda p: p["name"])
    if plugins:
        lines = [
            "| Skill | Categoria | O que faz | Instalar |",
            "|-------|-----------|-----------|----------|",
        ]
        for p in plugins:
            inst = f"`/plugin install {p['name']}@{MARKETPLACE_NAME}`"
            lines.append(
                f"| [`{p['name']}`](plugins/{p['name']}/) | {p.get('category', '-')} "
                f"| {short_desc(p['description'])} | {inst} |"
            )
        table = "\n".join(lines)
    else:
        table = "_Nenhuma skill publicada ainda. Use `make sync SKILL=<nome>` para adicionar a primeira._"

    text = README_FILE.read_text(encoding="utf-8")
    if README_START not in text or README_END not in text:
        raise SystemExit("ERRO: marcadores SKILLS:START/END ausentes no README.md")
    head, rest = text.split(README_START, 1)
    _, tail = rest.split(README_END, 1)
    README_FILE.write_text(
        f"{head}{README_START}\n\n{table}\n\n{README_END}{tail}", encoding="utf-8"
    )


def bump_version(version: str, part: str) -> str:
    try:
        major, minor, patch = (int(x) for x in version.split("."))
    except ValueError:
        major, minor, patch = 0, 1, 0
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="copia/atualiza uma skill local como plugin")
    p_sync.add_argument("skill")
    p_sync.add_argument("--from", dest="from_dir", help="diretório base das skills (padrão: ~/.claude/skills)")
    p_sync.add_argument("--category", help="categoria no marketplace")
    p_sync.add_argument("--bump", choices=["major", "minor", "patch"], help="incrementa a versão do plugin")
    p_sync.add_argument("--dry-run", action="store_true")
    p_sync.set_defaults(func=cmd_sync)

    p_imp = sub.add_parser("import", help="traz uma skill do repositório para ~/.claude/skills (para editar)")
    p_imp.add_argument("skill")
    p_imp.add_argument("--to", dest="to_dir", help="diretório base de destino (padrão: ~/.claude/skills)")
    p_imp.add_argument("--force", action="store_true", help="sobrescreve a versão local existente")
    p_imp.add_argument("--dry-run", action="store_true")
    p_imp.set_defaults(func=cmd_import)

    p_rm = sub.add_parser("remove", help="remove um plugin do repositório")
    p_rm.add_argument("skill")
    p_rm.add_argument("--dry-run", action="store_true")
    p_rm.set_defaults(func=cmd_remove)

    sub.add_parser("list", help="lista skills locais e quais já estão publicadas").set_defaults(func=cmd_list)
    sub.add_parser("readme", help="regenera só a tabela do README").set_defaults(func=cmd_readme)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
