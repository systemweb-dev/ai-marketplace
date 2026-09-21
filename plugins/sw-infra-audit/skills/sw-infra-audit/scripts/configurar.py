#!/usr/bin/env python3
"""Modo configurar: o único que escreve fora da pasta do relatório.

Nesta versão: `config --explicar`. `migrar` e `aceitar` entram na Task 12.
"""
import argparse
import re
import json
import sys
from pathlib import Path

from lib import alvos as alvos_mod
from lib.config import (ARQUIVO_DO_PROJETO, ConfigInvalida, caminho_do_projeto,
                        caminho_dos_alvos, carregar, exigir_pasta_protegida)

EXIT_OK, EXIT_ERRO = 0, 2

# o alvos.toml não deveria ter segredo, mas se alguém colar um, não é aqui que ele vaza
PARECE_SEGREDO = re.compile(r"senha|password|token|secret|pass|key|credential", re.IGNORECASE)

PADRAO_DA_SKILL = Path(__file__).resolve().parent.parent / "default.toml"
# onde a versão anterior guardava os alvos; `migrar` traz o conteúdo para o projeto
LEGADO_NO_HOME = Path.home() / ".config" / "sw-infra-audit" / "alvos.toml"


def _caminhos(args):
    padrao = Path(args.padrao) if args.padrao else PADRAO_DA_SKILL
    projeto = caminho_do_projeto(getattr(args, "projeto", None))
    return (padrao, caminho_dos_alvos(padrao=padrao, projeto=projeto,
                                      explicito=getattr(args, "infra", None)), projeto)


def explicar(args) -> int:
    padrao, infra, projeto = _caminhos(args)
    try:
        exigir_pasta_protegida(infra)
        cfg = carregar(padrao=padrao, infra=infra, projeto=projeto)
        declarados, avisos = alvos_mod.ler(infra)
    except (ConfigInvalida, alvos_mod.AlvoInvalido) as erro:
        print(str(erro), file=sys.stderr)
        return EXIT_ERRO

    print(f"padrão:  {padrao}\ninfra:   {infra}\nprojeto: {projeto}\n")
    print("chave                                valor                origem")
    for chave, valor, origem in cfg.explicar():
        mostrado = "***" if PARECE_SEGREDO.search(chave) else str(valor)
        print(f"{chave:<36} {mostrado:<20} {origem}")
    escolhidos = cfg.alvos_escolhidos()
    print("\nalvos declarados na infra:")
    for alvo in declarados:
        marca = "•" if not escolhidos or alvo["nome"] in escolhidos else " "
        print(f" {marca} {alvo['nome']:<24} {alvo['tipo']}")
    if escolhidos:
        print(f"\nescolhidos por este projeto: {', '.join(escolhidos)}")
    for aceite in cfg.aceites():
        print(f"aceite ({aceite['origem']}): {aceite.get('alvo')} · {aceite.get('regra')} · "
              f"revisar em {aceite.get('revisar_em')}")
    for aviso in avisos:
        print(f"aviso: {aviso}")
    return EXIT_OK


from calendar import monthrange
from datetime import date
from lib.runner import run


def contexts_docker():
    """Lista os contexts para a migração. Só leitura, pelo runner."""
    import json as _json
    saida = run(["docker", "context", "ls", "--format", "{{json .}}"], timeout=10)
    achados = []
    for linha in saida.splitlines():
        if not linha.strip():
            continue
        dados = _json.loads(linha)
        achados.append({"nome": dados.get("Name"), "endpoint": dados.get("DockerEndpoint", "")})
    return achados


def _garantir_ignorado(destino) -> bool:
    """A pasta do alvos.toml precisa estar no .gitignore ANTES do arquivo existir.

    Acrescentar a linha é seguro (ignorar nunca publica nada) e é o único jeito de o arquivo
    de conexão não nascer versionado. Fora de repositório não há nada a fazer.
    """
    from lib import ignorado as ignorado_mod
    pasta = destino.parent
    if not ignorado_mod.em_repositorio("."):
        return True
    if ignorado_mod.ignorado(f"{pasta}/") or ignorado_mod.ignorado(str(destino)):
        return True
    ignorar(argparse.Namespace(repo=".", pasta=str(pasta)))
    return ignorado_mod.ignorado(f"{pasta}/") or ignorado_mod.ignorado(str(destino))


def migrar(args) -> int:
    _, destino, _ = _caminhos(args)
    if destino.exists():
        print(f"{destino} já existe — não sobrescrevo. Acrescente os alvos à mão, ou aponte "
              f"--infra para outro caminho.", file=sys.stderr)
        return EXIT_ERRO

    destino.parent.mkdir(parents=True, exist_ok=True)
    if not _garantir_ignorado(destino):
        print(f"não consegui garantir que {destino.parent}/ está fora do git — o alvos.toml "
              f"guarda conexão e não pode nascer versionado.", file=sys.stderr)
        return EXIT_ERRO

    if LEGADO_NO_HOME.exists():     # quem já tinha alvos no home não recomeça do zero
        conteudo = LEGADO_NO_HOME.read_text(encoding="utf-8")
        origem = f"copiado de {LEGADO_NO_HOME} — pode apagar o antigo"
    else:
        linhas = ["# Alvos da sw-infra-audit. Mora na pasta do relatório, que fica fora do git.",
                  "# A senha nunca vem aqui: declare o NOME da variável de ambiente em senha_env.", ""]
        for ctx in contexts_docker():
            linhas += ["[[alvo]]", f'nome = "{ctx["nome"]}"', 'tipo = "docker"',
                       f'context = "{ctx["nome"]}"',
                       "# metricas_url = \"http://host:9090\"   # opcional; veja `alvos --sugerir`", ""]
        conteudo = "\n".join(linhas)
        origem = f"{conteudo.count('[[alvo]]')} alvo(s) docker dos seus contexts"

    destino.write_text(conteudo, encoding="utf-8")
    destino.chmod(0o600)
    print(f"{destino} criado ({origem}). Revise antes de auditar.")
    return EXIT_OK


def revisar_em(desde, meses):
    """`desde` mais `meses`, grudando no último dia quando o mês de destino é mais curto:
    31/03 + 6 meses = 30/09, nunca "31/09". Data que não existe no calendário faz a auditoria
    seguinte morrer ao ler o aceite — o registro do risco derrubando quem ele deveria explicar."""
    inicio = date.fromisoformat(desde)
    corrido = inicio.month - 1 + meses
    ano, mes = inicio.year + corrido // 12, corrido % 12 + 1
    return date(ano, mes, min(inicio.day, monthrange(ano, mes)[1])).isoformat()


def aceitar(args) -> int:
    if not (args.motivo or "").strip():
        print("aceitar exige --motivo: aceite sem justificativa é achado escondido.", file=sys.stderr)
        return EXIT_ERRO
    projeto = caminho_do_projeto(args.projeto)
    desde = args.desde or date.today().isoformat()
    try:                                    # antes de tocar no arquivo: entrada ruim não escreve
        revisar = revisar_em(desde, args.meses)
    except ValueError:
        print(f"--desde precisa ser uma data AAAA-MM-DD, veio {desde!r}", file=sys.stderr)
        return EXIT_ERRO
    # `json.dumps` produz uma string básica de TOML válida (aspas, barra e quebra de linha
    # escapadas). O bloco era montado com f-string crua: um motivo com aspas quebrava o
    # config.toml inteiro, e uma quebra de linha no motivo podia escrever outra chave.
    campos = [("alvo", args.alvo), ("componente", args.componente), ("regra", args.regra),
              ("objeto", args.objeto), ("motivo", args.motivo.strip()), ("desde", desde),
              ("revisar_em", revisar)]
    bloco = ["", "[[aceite]]"] + [f"{chave} = {json.dumps(valor, ensure_ascii=False)}"
                                  for chave, valor in campos if valor]
    projeto.parent.mkdir(parents=True, exist_ok=True)
    atual = projeto.read_text(encoding="utf-8") if projeto.exists() else ""
    projeto.write_text(atual.rstrip("\n") + "\n" + "\n".join(bloco) + "\n", encoding="utf-8")
    print(f"aceite registrado em {projeto} · revisar em {revisar}")
    return EXIT_OK


def candidatos_de_metricas(context):
    """Usa a descoberta que já existe para PROPOR uma `metricas_url` — sem alcançar host nenhum.

    Todo comando leva o context pedido: sem isso, a proposta sairia do daemon LOCAL e ofereceria
    as métricas da máquina de quem rodou como se fossem as do cluster.
    """
    from lib import discover
    from lib.coletores.docker import assemble_report, host_from_context

    def rodar(cmd, timeout, errors=None):
        return run(cmd, timeout, errors, context=context)

    bruto = assemble_report(run_fn=rodar, timeout=10, context=context,
                            generated_at="", connected_node=None)
    return discover.propose(bruto, host_from_context(context, 10))


def sugerir(args) -> int:
    achados = candidatos_de_metricas(args.context)
    if not achados:
        print("nenhum candidato a métricas encontrado neste context")
        return EXIT_OK
    print("candidatos para `metricas_url` (cole no alvos.toml o que fizer sentido):")
    for candidato in achados:
        # sem host no endpoint (socket local) a URL não existe — dizer isso é melhor que estourar
        url = candidato["url"] or "(sem host no endpoint deste context)"
        print(f"  {url:<48} {candidato['por_que']}")
    return EXIT_OK


def linhas_de_ignore(pasta):
    """Esconde o CONTEÚDO da pasta e reabre um arquivo: o `config.toml` é versionado de
    propósito — escolha de alvos e riscos aceitos passam por revisão em PR."""
    return [f"{pasta}/*", f"!{pasta}/{ARQUIVO_DO_PROJETO}"]


def ignorar(args) -> int:
    """Acerta o .gitignore da pasta do relatório. É escrita em arquivo versionado: por isso mora
    aqui, no modo configurar, e não no modo auditar."""
    repo = Path(args.repo)
    pasta = args.pasta.rstrip("/")
    gi = repo / ".gitignore"
    atual = gi.read_text(encoding="utf-8") if gi.exists() else ""
    linhas = atual.splitlines()

    # `docs/infra/` ignora o DIRETÓRIO: o git nem entra nele, e nenhuma negação salva um arquivo
    # lá dentro. A forma antiga não convive com a nova — é substituída.
    linhas = [linha for linha in linhas if linha.strip() not in (f"{pasta}/", pasta)]
    novas = [linha for linha in linhas_de_ignore(pasta) if linha not in linhas]
    if not novas and linhas == atual.splitlines():
        print(f"{pasta}/ já está no .gitignore, com o {ARQUIVO_DO_PROJETO} de fora")
        return EXIT_OK

    gi.write_text("\n".join(linhas + novas).strip("\n") + "\n", encoding="utf-8")
    print(f"{pasta}/ ignorado no .gitignore (menos o {ARQUIVO_DO_PROJETO}, que é versionado)")
    return EXIT_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Configuração da sw-infra-audit.")
    sub = ap.add_subparsers(dest="comando", required=True)
    cfg = sub.add_parser("config", help="inspecionar a configuração efetiva")
    cfg.add_argument("--explicar", action="store_true", required=True)
    for parser in (cfg,):
        parser.add_argument("--padrao", default=None)
        parser.add_argument("--infra", default=None)
        parser.add_argument("--projeto", default=None)
    mig = sub.add_parser("migrar", help="cria o primeiro alvos.toml na pasta do relatório")
    mig.add_argument("--infra", default=None)
    mig.add_argument("--padrao", default=None)
    mig.add_argument("--projeto", default=None)

    ace = sub.add_parser("aceitar", help="registra um risco aceito no arquivo do projeto")
    ace.add_argument("--projeto", default=None)
    ace.add_argument("--alvo", required=True)
    ace.add_argument("--regra", required=True)
    ace.add_argument("--componente", default=None,
                     help="só os achados deste componente (sem ele, vale para o alvo inteiro)")
    ace.add_argument("--objeto", default=None,
                     help="só este objeto; em fila, `nome@vhost` (ex.: emails@staging)")
    ace.add_argument("--motivo", required=True)
    ace.add_argument("--desde", default=None)
    ace.add_argument("--meses", type=int, default=6, help="prazo até a revisão (padrão: 6 meses)")

    alv = sub.add_parser("alvos", help="inspecionar e propor valores para os alvos")
    alv.add_argument("--sugerir", action="store_true", required=True)
    alv.add_argument("--context", required=True, help="context docker de onde partir")

    ign = sub.add_parser("ignorar", help="põe a pasta do relatório no .gitignore")
    ign.add_argument("--repo", default=".")
    ign.add_argument("--pasta", default="docs/infra")

    args = ap.parse_args(argv)
    return {"config": explicar, "migrar": migrar, "aceitar": aceitar, "alvos": sugerir,
            "ignorar": ignorar}[args.comando](args)


if __name__ == "__main__":
    raise SystemExit(main())
