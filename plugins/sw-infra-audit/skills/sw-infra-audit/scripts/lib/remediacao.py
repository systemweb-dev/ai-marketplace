"""Catálogo de remediação: o que fazer, em arquivo versionado, não em prosa gerada na hora.

Texto gerado varia a cada rodada e não passa por revisão. Aqui o mínimo é garantido e revisável
em pull request; o agente pode ENRIQUECER a análise por cima, nunca substituir isto.

**Os comandos são para EXIBIR, nunca para executar.** A auditoria é só leitura; quem decide
aplicar é o dono, depois de ler o "quando NÃO fazer".
"""
import re
from pathlib import Path

# os quatro blocos são obrigatórios: "como resolver" sem "como confirmar" deixa o leitor sem
# saber se resolveu, e sem "quando NÃO fazer" transforma exceção legítima em erro.
BLOCOS = {"Por que importa": "por_que_importa",
          "Como resolver": "como_resolver",
          "Como confirmar": "como_confirmar",
          "Quando NÃO fazer": "quando_nao_fazer"}
PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "remediacao"


class RemediacaoInvalida(Exception):
    """Arquivo de remediação fora do formato de quatro blocos."""


def carregar_arquivo(caminho):
    caminho = Path(caminho)
    texto = caminho.read_text(encoding="utf-8")
    cabecalho = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if not cabecalho:
        raise RemediacaoInvalida(f"{caminho.name}: falta o cabeçalho com `regra` e `titulo`")
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", cabecalho.group(1), re.M))
    if not meta.get("regra") or not meta.get("titulo"):
        raise RemediacaoInvalida(f"{caminho.name}: o cabeçalho precisa de `regra` e `titulo`")
    if meta["regra"] != caminho.stem:
        raise RemediacaoInvalida(f"{caminho.name}: o arquivo é da regra {caminho.stem!r} mas o "
                                 f"cabeçalho diz {meta['regra']!r}")

    corpo = texto[cabecalho.end():]
    secoes = {titulo.strip(): conteudo.strip() for titulo, conteudo in
              re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", corpo, re.S | re.M)}
    faltando = [titulo for titulo in BLOCOS if titulo not in secoes]
    if faltando:
        raise RemediacaoInvalida(f"{caminho.name}: falta o bloco {faltando[0]!r}")

    bloco = {"regra": meta["regra"], "titulo": meta["titulo"]}
    bloco.update({chave: secoes[titulo] for titulo, chave in BLOCOS.items()})
    return bloco


def disponiveis(pasta=PASTA):
    return {arquivo.stem for arquivo in Path(pasta).glob("*.md")}


def para(regra, pasta=PASTA):
    """O bloco daquela regra, ou None.

    Regra sem arquivo não quebra o relatório — quebra o teste, que é onde esse erro tem que
    aparecer, antes de chegar em quem lê.
    """
    caminho = Path(pasta) / f"{regra}.md"
    return carregar_arquivo(caminho) if caminho.exists() else None
