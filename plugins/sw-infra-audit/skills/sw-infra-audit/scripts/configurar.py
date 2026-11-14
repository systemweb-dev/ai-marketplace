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
                       "# metricas_url = \"http://host:9090\"   # opcional; veja `alvos --sugerir`",
                       "# logs_url = \"http://host:3100\"       # opcional; Loki com o log de acesso do proxy",
                       ""]
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
        # os campos são os que o `discover.propose` devolve; inventar um aqui foi o que fez o
        # comando morrer de KeyError em todo cluster que tinha um Prometheus.
        alcance = "porta publicada" if candidato["published"] else "porta interna (não publicada)"
        print(f"  {url:<48} {candidato['service']} · {alcance}")
        print(f"  {'':<48} {candidato['provides']}")
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


def _alvo_host(args):
    _, infra, _ = _caminhos(args)
    lidos, _ = alvos_mod.ler(infra)
    alvo = next((a for a in lidos if a["nome"] == args.alvo), None)
    if alvo is None or alvo["tipo"] != "host":
        raise alvos_mod.AlvoInvalido(f"{args.alvo!r} não é um alvo host em {infra}")
    return alvo, infra


def _ler_fontes(alvo):
    """As três fontes da descoberta; None numa delas = não medida. None no todo = sem sessão."""
    from lib import catalogo_host, runner

    comandos, erros = catalogo_host.carregar()["comandos"], []
    rodar = lambda chave: runner.run_ssh(alvo["ssh_destino"], alvo.get("porta"), comandos[chave],
                                         20, erros)
    if rodar("usuario") is None:
        return None, (erros[0]["reason"] if erros else "o ssh falhou sem detalhe")
    return {chave: rodar(chave) for chave in ("servicos", "portas", "containers")}, None


def descobrir(args) -> int:
    from lib import catalogo_host, descoberta, produtos, redact

    try:
        alvo, infra = _alvo_host(args)
    except (alvos_mod.AlvoInvalido, ConfigInvalida) as erro:
        print(str(erro), file=sys.stderr)
        return EXIT_ERRO
    saidas, motivo = _ler_fontes(alvo)
    if saidas is None:
        print(redact.scrub_text(motivo), file=sys.stderr)
        return EXIT_ERRO
    resultado = descoberta.descobrir(saidas, produtos.carregar(), catalogo_host.carregar()["ignorar"])
    if not args.gravar:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return EXIT_OK
    return _gravar_descobertos(alvo, infra, resultado, args)


def _gravar_descobertos(alvo, infra, resultado, args) -> int:
    from datetime import date

    from lib import gravacao_alvos
    from lib.config import exigir_pasta_protegida

    pedidos = [n.strip() for n in args.gravar.split(",") if n.strip()]
    papeis = dict(p.split("=", 1) for p in args.papel if "=" in p)
    por_nome = {c["nome"]: c for c in resultado["candidatos"] if c["gravavel"]}
    faltando = [n for n in pedidos if n not in por_nome]
    if faltando:
        print(f"não há candidato gravável com nome {', '.join(faltando)}", file=sys.stderr)
        return EXIT_ERRO
    ja = {c.get("origem") for c in alvo["componente"]}
    novos = [dict(por_nome[n], papel=papeis.get(n, por_nome[n]["papel"]))
             for n in pedidos if por_nome[n]["origem"] not in ja]
    if not novos:
        print("nada novo para gravar: todos já estão no alvos.toml")
        return EXIT_OK
    try:
        exigir_pasta_protegida(infra)
    except ConfigInvalida as erro:
        print(str(erro), file=sys.stderr)
        return EXIT_ERRO
    original = Path(infra).read_text(encoding="utf-8")
    backup = Path(f"{infra}.bak")
    # nasce 600: escrever antes do chmod deixaria o inventário legível por outros usuários da
    # máquina na janela entre os dois
    backup.touch(mode=0o600, exist_ok=True)
    backup.chmod(0o600)
    backup.write_text(original, encoding="utf-8")
    nomes_antes = [a["nome"] for a in alvos_mod.ler(infra)[0]]
    esperado = [c.get("origem") for c in alvo["componente"]] + [c["origem"] for c in novos]
    try:
        Path(infra).write_text(gravacao_alvos.inserir(original, alvo["nome"], novos,
                                                      date.today().isoformat()), encoding="utf-8")
        lidos = alvos_mod.ler(infra)[0]
        relido = next(a for a in lidos if a["nome"] == alvo["nome"])
        if [a["nome"] for a in lidos] != nomes_antes or \
                [c.get("origem") for c in relido["componente"]] != esperado:
            raise gravacao_alvos.GravacaoInvalida("a releitura não trouxe exatamente o pedido")
    except (gravacao_alvos.GravacaoInvalida, alvos_mod.AlvoInvalido, StopIteration) as erro:
        Path(infra).write_text(original, encoding="utf-8")
        print(f"gravação desfeita: {erro}. O arquivo voltou ao original; cópia em {backup}",
              file=sys.stderr)
        return EXIT_ERRO
    print(f"gravados {len(novos)} componente(s) em {infra}; cópia anterior em {backup}")
    return EXIT_OK

USUARIO_DE_LEITURA = re.compile(r"[A-Za-z0-9._@-]{1,64}")
NOME_DE_VARIAVEL = re.compile(r"[A-Z_][A-Z0-9_]{0,63}")


def _campos_de_leitura(args, componente):
    """Os `(campo, valor)` a gravar, ou ValueError com a frase para o dono. Nada aqui toca arquivo."""
    from lib import catalogo_produto
    from lib.vagas import pasta_valida

    if componente.get("papel") not in ("banco", "cache", "busca"):
        raise ValueError(f"leitura só vale para componente de papel banco, cache ou busca; "
                         f"{componente['nome']!r} tem papel {componente.get('papel')!r}")
    campos = [("leitura", args.modo)]
    if args.modo == "senha":
        if not args.usuario or not args.senha_env:
            raise ValueError("--modo senha exige --usuario e --senha-env (o NOME da variável de "
                             "ambiente, nunca a senha)")
        catalogo = catalogo_produto.do_produto(componente.get("produto"))
        if catalogo is None or "senha" not in catalogo["cliente"]:
            raise ValueError(f"o produto {componente.get('produto')!r} não tem leitura com senha "
                             f"nesta versão (só MariaDB e MySQL)")
        if not USUARIO_DE_LEITURA.fullmatch(args.usuario):
            raise ValueError("--usuario só com letras, números, ponto, hífen, sublinhado e @")
        if not NOME_DE_VARIAVEL.fullmatch(args.senha_env):
            raise ValueError("--senha-env é o NOME de uma variável de ambiente, em maiúsculas "
                             "(ex.: SENHA_BANCO_01)")
        campos += [("usuario", args.usuario), ("senha_env", args.senha_env)]
    elif args.usuario or args.senha_env:
        raise ValueError("--usuario e --senha-env só valem com --modo senha")
    if args.modo == "container" and not str(componente.get("origem") or "").startswith("container:"):
        raise ValueError("--modo container só vale para componente com origem container:<nome>")
    if args.backup_pasta is not None:
        if not pasta_valida(args.backup_pasta):
            raise ValueError("--backup-pasta precisa ser caminho absoluto só com letras, números, "
                             "ponto, hífen, sublinhado e barra, sem `..`")
        campos.append(("backup_pasta", args.backup_pasta))
    if args.backup_max_dias is not None:
        if args.backup_pasta is None and not componente.get("backup_pasta"):
            raise ValueError("--backup-max-dias precisa de --backup-pasta")
        if not 1 <= args.backup_max_dias <= 365:
            raise ValueError("--backup-max-dias vai de 1 a 365")
        campos.append(("backup_max_dias", args.backup_max_dias))
    return campos


def leitura(args) -> int:
    from lib import gravacao_alvos

    try:
        alvo, infra = _alvo_host(args)
        componente = next((c for c in alvo["componente"] if c["nome"] == args.componente), None)
        if componente is None:
            raise alvos_mod.AlvoInvalido(f"o alvo {args.alvo!r} não tem componente "
                                         f"{args.componente!r}")
        campos = _campos_de_leitura(args, componente)
        exigir_pasta_protegida(infra)
        original = Path(infra).read_text(encoding="utf-8")
        novo = gravacao_alvos.acrescentar_campos(original, alvo["nome"], componente["nome"], campos)
    except (alvos_mod.AlvoInvalido, ConfigInvalida, ValueError, gravacao_alvos.GravacaoInvalida) as erro:
        print(str(erro), file=sys.stderr)
        return EXIT_ERRO
    backup = Path(f"{infra}.bak")
    backup.touch(mode=0o600, exist_ok=True)
    backup.chmod(0o600)
    backup.write_text(original, encoding="utf-8")
    novos = dict(campos)
    esperado = [{**a, "componente": [{**c, **novos} if (a["nome"] == alvo["nome"]
                                                        and c["nome"] == componente["nome"]) else c
                                     for c in a["componente"]]}
                for a in alvos_mod.ler(infra)[0]]
    try:
        Path(infra).write_text(novo, encoding="utf-8")
        if alvos_mod.ler(infra)[0] != esperado:
            raise gravacao_alvos.GravacaoInvalida("a releitura não trouxe exatamente o pedido")
    except (gravacao_alvos.GravacaoInvalida, alvos_mod.AlvoInvalido) as erro:
        Path(infra).write_text(original, encoding="utf-8")
        print(f"gravação desfeita: {erro}. O arquivo voltou ao original; cópia em {backup}",
              file=sys.stderr)
        return EXIT_ERRO
    print(f"leitura de {componente['nome']} gravada ({', '.join(c for c, _ in campos)}); cópia "
          f"anterior em {backup}")
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

    des = sub.add_parser("descobrir", help="lista (e, com --gravar, grava) o que roda num host")
    des.add_argument("--alvo", required=True)
    des.add_argument("--gravar", default=None, help="nomes separados por vírgula")
    des.add_argument("--papel", action="append", default=[], help="nome=papel, repetível")
    des.add_argument("--infra", default=None)
    des.add_argument("--padrao", default=None)
    des.add_argument("--projeto", default=None)
    lei = sub.add_parser("leitura", help="grava como a skill lê um componente de host")
    lei.add_argument("--alvo", required=True)
    lei.add_argument("--componente", required=True)
    lei.add_argument("--modo", required=True, choices=alvos_mod.LEITURAS)
    lei.add_argument("--usuario", default=None)
    lei.add_argument("--senha-env", dest="senha_env", default=None,
                     help="o NOME da variável de ambiente, nunca a senha")
    lei.add_argument("--backup-pasta", dest="backup_pasta", default=None)
    lei.add_argument("--backup-max-dias", dest="backup_max_dias", type=int, default=None)
    lei.add_argument("--infra", default=None)
    lei.add_argument("--padrao", default=None)
    lei.add_argument("--projeto", default=None)

    ign = sub.add_parser("ignorar", help="põe a pasta do relatório no .gitignore")
    ign.add_argument("--repo", default=".")
    ign.add_argument("--pasta", default="docs/infra")

    args = ap.parse_args(argv)
    return {"config": explicar, "migrar": migrar, "aceitar": aceitar, "alvos": sugerir,
            "ignorar": ignorar, "descobrir": descobrir, "leitura": leitura}[args.comando](args)


if __name__ == "__main__":
    raise SystemExit(main())
