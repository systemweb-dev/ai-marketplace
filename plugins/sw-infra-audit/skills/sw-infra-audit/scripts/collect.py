#!/usr/bin/env python3
"""Modo auditar: confirma os alvos, chama um coletor por tipo e grava o report.json v3.

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
from lib.orcamento import Prazo
from lib.config import ConfigInvalida, caminho_do_projeto, caminho_dos_alvos, carregar,\
    exigir_pasta_protegida

EXIT_OK, EXIT_PARADA = 0, 2

PADRAO_DA_SKILL = Path(__file__).resolve().parent.parent / "default.toml"


def adaptadores_padrao():
    """O registro de verdade. Importado aqui dentro para o módulo não puxar rede à toa — e
    para o teste conseguir rodar com adaptadores falsos."""
    from lib import adaptadores
    return adaptadores.todos()


def responder(componente, contexto, adaptadores, prazo):
    """Faz as perguntas do papel do componente e guarda a resposta com a fonte.

    Cada pergunta tem o seu contorno: bug de adaptador vira `erro_interno` DAQUELA pergunta e a
    coleta segue. Sem isso, uma pergunta quebrada apagaria o inventário inteiro do alvo.

    A ordem dos adaptadores é a de especificidade: o primeiro que souber responder vence, e o
    motivo guardado é o do primeiro que tentou — é ele que explica o que falta declarar.
    """
    from lib.perguntas import do_papel

    for pergunta in do_papel(componente.get("papel", "app")):
        if prazo.esgotado():
            componente["respostas"].append({"pergunta": pergunta["id"], "sem_dados": True,
                                            "motivo": prazo.motivo()})
            continue
        contexto_pergunta = dict(contexto, timeout=prazo.timeout(contexto["timeout"]))
        resposta = None
        for adaptador in adaptadores:
            try:
                candidata = adaptador.perguntar(pergunta["id"], componente, contexto_pergunta)
            except Exception as erro:              # noqa: BLE001 — bug do adaptador, não falha de acesso
                candidata = {"pergunta": pergunta["id"], "erro_interno": True,
                             "motivo": f"{adaptador.ID}: {type(erro).__name__}: {erro}"}
            if not candidata.get("sem_dados"):
                resposta = candidata
                break
            resposta = resposta or candidata
        if resposta is not None:
            componente["respostas"].append(resposta)
    return componente


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
CAMPOS_DO_COLETOR = ("saude", "dimensoes", "fatos", "achados", "componentes")


def peneirar_componentes(registro):
    """Deixa passar só componente que é dicionário com nome — o resto vira `nao_coletado`.

    A promoção mexe em `componente["nome"]` e `componente["achados"]`: sem esta peneira, um
    coletor que devolvesse `["proxy"]` derrubaria a auditoria inteira com AttributeError, o
    oposto do que este módulo promete.
    """
    validos = []
    for bruto in registro.get("componentes", []):
        if not isinstance(bruto, dict) or not isinstance(bruto.get("nome"), str):
            registro["nao_coletado"].append(report_mod.na(
                f"componente ignorado: esperava um bloco com nome, veio {type(bruto).__name__}"))
            continue
        bruto.setdefault("papel", "app")
        bruto.setdefault("respostas", [])
        bruto.setdefault("achados", [])
        bruto.setdefault("analise", "")
        validos.append(bruto)
    registro["componentes"] = validos
    return registro


def promover_achados(registro):
    """Achado nasce no componente e sobe para o alvo, carregando de onde veio.

    O alvo é a fonte única para ordenação, inventário e histórico; o componente guarda a sua
    cópia para a ficha dele no relatório. Assim quem aceita um risco pode mirar o alvo inteiro
    ou um componente só.
    """
    for componente in registro.get("componentes", []):
        for achado in componente.get("achados", []):
            achado.setdefault("alvo", registro["nome"])
            achado["componente"] = componente["nome"]
            registro["achados"].append(dict(achado))
    return registro


def coletar_alvo(alvo, coletor, contexto, adaptadores=()):
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

    peneirar_componentes(registro)
    prazo = Prazo(contexto.get("orcamento", 120))
    for componente in registro["componentes"]:
        responder(componente, contexto, adaptadores, prazo)
    promover_achados(registro)

    extras = resultado.get("nao_coletado", [])
    if isinstance(extras, list):
        registro["nao_coletado"].extend(e for e in extras if isinstance(e, dict))
    elif extras:
        registro["nao_coletado"].append(report_mod.na("o coletor devolveu nao_coletado inválido"))
    return registro


def main(argv=None, coletores=None, adaptadores=None) -> int:
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
    projeto = caminho_do_projeto(args.projeto)

    try:
        # os alvos moram na pasta do relatório, dentro do projeto: só pode se o git a ignora
        infra = caminho_dos_alvos(padrao=padrao, projeto=projeto, explicito=args.infra)
        exigir_pasta_protegida(infra)
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
    adaptadores = adaptadores_padrao() if adaptadores is None else adaptadores
    def limite(chave, padrao):
        """`or` não serve aqui: `0` é um valor que o dono pode ter escrito de propósito, e
        `0 or 120` devolve 120 — o limite configurado sumiria sem uma palavra."""
        valor = cfg.valor(chave)
        return padrao if valor is None else valor

    # sem padrão, um limite ausente viraria espera infinita no coletor
    contexto = {"timeout": limite("limites.timeout_por_comando", 20),
                "orcamento": limite("limites.orcamento_por_alvo", 120),
                "http_timeout": limite("limites.http_timeout", 8),
                # a janela dos insights é ancorada no --at pelo adaptador; aqui só o tamanho
                "janela": limite("insights.janela", "24h"),
                "at": args.at}

    relatorio = report_mod.novo(generated_at=args.at)
    for alvo in escolhidos:
        if alvo["nome"] not in confirmados:
            registro = report_mod.novo_alvo(alvo["nome"], alvo["tipo"], onde_de(alvo))
            registro["nao_coletado"].append(report_mod.na("alvo não confirmado nesta execução"))
            registro["coletado"] = False
            relatorio["alvos"].append(registro)
            continue
        registro = coletar_alvo(alvo, coletores.get(alvo["tipo"]), contexto, adaptadores)
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

    try:
        # allow_nan=False: NaN e Infinity são aceitos pelo json do Python e REJEITADOS por
        # todo o resto do mundo. Melhor parar dizendo o que veio errado do que entregar um
        # arquivo que só o Python relê.
        conteudo = json.dumps(relatorio, ensure_ascii=False, indent=1, allow_nan=False)
    except ValueError as erro:
        print(f"o relatório trouxe um valor que não é um número representável em JSON "
              f"({erro}); nada foi gravado", file=sys.stderr)
        return EXIT_PARADA

    saida = Path(args.out)
    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / "report.json"
    destino.write_text(conteudo, encoding="utf-8")

    print(f"report.json: {destino}")
    for alvo in relatorio["alvos"]:
        print(f"  {alvo['saude']:<10} {alvo['nome']:<24} {alvo['tipo']}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
