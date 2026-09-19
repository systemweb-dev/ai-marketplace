#!/usr/bin/env python3
"""Modo auditar: confirma os alvos, chama um coletor por tipo e grava o report.json v2.

Não escreve nada fora da pasta de saída. Falha de coleta nunca vira achado: vira `nao_coletado`
com o motivo — confundir "não consegui ver" com "está ruim" é o jeito mais fácil de mentir.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from lib import alvos as alvos_mod
from lib import report as report_mod
from lib.falhas import FalhaDeColeta
from lib.config import ConfigInvalida, carregar

EXIT_OK, EXIT_PARADA = 0, 2

PADRAO_DA_SKILL = Path(__file__).resolve().parent.parent / "default.toml"
INFRA_PADRAO = Path.home() / ".config" / "sw-infra-audit" / "alvos.toml"
PROJETO_PADRAO = Path(".sw-infra-audit.toml")


def coletores_padrao():
    """O registro de verdade. Importado aqui dentro para o módulo não puxar coletor à toa —
    e para o teste conseguir rodar o orquestrador com coletores falsos."""
    from lib.coletores import docker as coletor_docker
    from lib.coletores import http as coletor_http

    return {"docker": coletor_docker.coletar, "http": coletor_http.coletar}


def onde_de(alvo):
    """Como o alvo é identificado no relatório — sem credencial, sempre."""
    if alvo["tipo"] == "docker":
        return f"context: {alvo['context']}"
    if alvo["tipo"] == "http":
        return alvo["url"]
    return alvo.get("host", "")


# o coletor só preenche estes campos: identidade do alvo é do orquestrador, não dele
CAMPOS_DO_COLETOR = ("saude", "dimensoes", "fatos", "achados")


def coletar_alvo(alvo, coletor, contexto):
    """Roda um coletor e traduz qualquer falha em `nao_coletado`.

    Nada que o coletor devolva pode derrubar a auditoria dos outros alvos, e nada que ele devolva
    pode reescrever `nome`, `tipo` ou `onde` — esses vão para o inventário e para a chave do
    histórico; deixá-los editáveis seria deixar o relatório mentir.
    """
    registro = report_mod.novo_alvo(alvo["nome"], alvo["tipo"], onde_de(alvo))
    if coletor is None:
        registro["nao_coletado"].append(report_mod.na(f"tipo {alvo['tipo']} sem coletor nesta versão"))
        return registro
    try:
        resultado = coletor(alvo, contexto)
        if not isinstance(resultado, dict):
            raise FalhaDeColeta(f"o coletor devolveu {type(resultado).__name__}, não um dicionário")
    except TimeoutError as erro:
        registro["nao_coletado"].append(report_mod.na(f"orçamento do alvo estourou: {erro}"))
        return registro
    except FalhaDeColeta as erro:
        registro["nao_coletado"].append(report_mod.na(str(erro)))
        return registro
    except Exception as erro:                      # noqa: BLE001 — bug do coletor, não falha de acesso
        registro["erro_interno"] = True
        registro["nao_coletado"].append(
            report_mod.na(f"erro interno do coletor {type(erro).__name__}: {erro}"))
        return registro

    for campo in CAMPOS_DO_COLETOR:
        if campo not in resultado:
            continue
        valor = resultado[campo]
        esperado = type(registro[campo])
        if not isinstance(valor, esperado):
            registro["nao_coletado"].append(report_mod.na(
                f"o coletor devolveu {campo} inválido ({type(valor).__name__})"))
            continue
        registro[campo] = valor

    extras = resultado.get("nao_coletado", [])
    if isinstance(extras, list):
        registro["nao_coletado"].extend(e for e in extras if isinstance(e, dict))
    elif extras:
        registro["nao_coletado"].append(report_mod.na("o coletor devolveu nao_coletado inválido"))
    return registro


def main(argv=None, coletores=None) -> int:
    ap = argparse.ArgumentParser(description="Auditoria read-only por alvos.")
    ap.add_argument("--out", required=True, help="pasta desta execução")
    ap.add_argument("--at", required=True, help="carimbo de tempo (injetado, para ser determinístico)")
    ap.add_argument("--confirmar", nargs="*", default=[], help="nomes dos alvos autorizados nesta rodada")
    ap.add_argument("--padrao", default=None)
    ap.add_argument("--infra", default=None)
    ap.add_argument("--projeto", default=None)
    args = ap.parse_args(argv)

    try:                                   # o carimbo vira a data que decide aceite vencido
        date.fromisoformat(args.at[:10])
    except ValueError:
        print(f"--at precisa começar com AAAA-MM-DD, veio {args.at!r}", file=sys.stderr)
        return EXIT_PARADA

    padrao = Path(args.padrao) if args.padrao else PADRAO_DA_SKILL
    infra = Path(args.infra) if args.infra else INFRA_PADRAO
    projeto = Path(args.projeto) if args.projeto else PROJETO_PADRAO

    try:
        cfg = carregar(padrao=padrao, infra=infra, projeto=projeto)
        declarados, avisos = alvos_mod.ler(infra)
        escolhidos = alvos_mod.selecionar(declarados, cfg.alvos_escolhidos())
    except (ConfigInvalida, alvos_mod.AlvoInvalido) as erro:
        print(str(erro), file=sys.stderr)
        return EXIT_PARADA

    for aviso in avisos:                    # antes do gate: sem alvos.toml, é isto que orienta
        print(f"aviso: {aviso}")

    confirmados = list(args.confirmar)
    desconhecidos = [n for n in confirmados if n not in {a["nome"] for a in escolhidos}]
    if desconhecidos:
        print(f"--confirmar cita alvo que não está na auditoria: {', '.join(desconhecidos)}",
              file=sys.stderr)
        return EXIT_PARADA
    if not confirmados:
        print("nenhum alvo confirmado: nada foi tocado. Confirme com --confirmar <nomes>.",
              file=sys.stderr)
        return EXIT_PARADA

    # sem registro explícito (linha de comando), usa os coletores de verdade
    coletores = coletores_padrao() if coletores is None else coletores
    # sem padrão, um limite ausente viraria espera infinita no coletor
    contexto = {"timeout": cfg.valor("limites.timeout_por_comando") or 20,
                "orcamento": cfg.valor("limites.orcamento_por_alvo") or 120,
                "http_timeout": cfg.valor("limites.http_timeout") or 8,
                "at": args.at}

    relatorio = report_mod.novo(generated_at=args.at)
    for alvo in escolhidos:
        if alvo["nome"] not in confirmados:
            registro = report_mod.novo_alvo(alvo["nome"], alvo["tipo"], onde_de(alvo))
            registro["nao_coletado"].append(report_mod.na("alvo não confirmado nesta execução"))
            registro["coletado"] = False
            relatorio["alvos"].append(registro)
            continue
        registro = coletar_alvo(alvo, coletores.get(alvo["tipo"]), contexto)
        registro["coletado"] = True
        relatorio["alvos"].append(registro)

    from lib import aceites as aceites_mod
    try:
        relatorio["aceites"] = aceites_mod.aplicar(relatorio["alvos"], cfg.aceites(),
                                                   hoje=args.at[:10])
    except ValueError as erro:        # aceite mal escrito: dizer qual linha arrumar, não um traceback
        print(f"aceite inválido: {erro}", file=sys.stderr)
        return EXIT_PARADA
    relatorio = report_mod.ordenar(relatorio)
    relatorio["inventario"] = report_mod.montar_inventario(relatorio)

    if cfg.valor("historico.comparar_com_anterior"):
        from lib import historico as hist
        anterior = hist.pasta_anterior(Path(args.out))
        if anterior is not None:
            relatorio["historico"] = hist.comparar(
                json.loads((anterior / "report.json").read_text(encoding="utf-8")),
                relatorio, nome_anterior=anterior.name)

    saida = Path(args.out)
    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / "report.json"
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"report.json: {destino}")
    for alvo in relatorio["alvos"]:
        print(f"  {alvo['saude']:<10} {alvo['nome']:<24} {alvo['tipo']}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
