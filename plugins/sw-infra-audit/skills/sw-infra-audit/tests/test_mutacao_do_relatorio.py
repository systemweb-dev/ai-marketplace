"""Quebrar cada trecho de propósito: a suíte TEM de cair, senão o trecho segue sem cobertura."""
import os
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
TESTES = "tests/test_correcoes_do_relatorio.py"
BUILD = "scripts/build_report.py"

# (nome, arquivo, trecho original, trecho mutado, teste que precisa cair)
MUTACOES = [
    ("outras recomendações ignora o corte", BUILD,
     "if not _so_em_contagem(itens, corte)}",
     "if True}",
     "test_outras_recomendacoes_recebem_a_de_regra_que_o_corte_escondeu"),
    ("outras recomendações deixa de filtrar", BUILD,
     'if r.get("regra") in regras:',
     "if False:",
     "test_outras_recomendacoes_recebem_a_de_regra_que_o_corte_escondeu"),
    ("_comandos sem escape no comando", BUILD,
     """comando = f'<pre>{_e(r.get("comando"))}</pre>'""",
     """comando = f'<pre>{r.get("comando")}</pre>'""",
     "test_comandos_escapa_titulo_e_comando"),
    ("_comandos sem escape no título", BUILD,
     """return f'<h4>{_e(r.get("titulo"))}</h4>{porque}{comando}{esforco}'""",
     """return f'<h4>{r.get("titulo")}</h4>{porque}{comando}{esforco}'""",
     "test_comandos_escapa_titulo_e_comando"),
    ("_faltou ignora nao_coletado", BUILD,
     'if nao_coletado_vigente(a) and a.get("nome")})',
     'if False and a.get("nome")})',
     "test_alvo_inteiro_sem_dados_aparece_na_linha_do_que_nao_foi_medido"),
    ("_faltou inclui quem ficou fora da rodada", BUILD,
     'return [a for a in alvos if a.get("coletado") is not False]',
     "return list(alvos)",
     "test_alvo_fora_da_rodada_fica_so_em_fora_desta_rodada"),
    ("_faltou deixa o alvo cair no corte", BUILD,
     "return sem_dados + categorias + ([_plural(servicos,",
     "return categorias + sem_dados + ([_plural(servicos,",
     "test_alvo_sem_dados_nao_sai_da_linha_cortado_pelos_componentes"),
    ("a capa corta sem dizer quantos", "scripts/lib/capa.py",
     """lista = f"{', '.join(visiveis)}{_e_mais(len(faltou), len(visiveis))}\"""",
     """lista = f"{', '.join(visiveis)}\"""",
     "test_a_capa_diz_quantos_ficaram_fora_da_linha_do_que_nao_foi_medido"),
    ("opcional com limiar no registro", "scripts/lib/perguntas.py",
     '_p("fila.filas", "fila", "Filas", "lista", unidade="mensagens", desempate="nome",',
     '_p("fila.filas", "fila", "Filas", "lista", unidade="mensagens", desempate="nome", opcional=True,',
     "test_nenhuma_pergunta_opcional_tem_limiar"),
]


@pytest.mark.parametrize("nome,arquivo,de,para,teste", MUTACOES, ids=[m[0] for m in MUTACOES])
def test_quebrar_o_trecho_derruba_o_teste(nome, arquivo, de, para, teste):
    alvo = RAIZ / arquivo
    original = alvo.read_text(encoding="utf-8")
    assert de in original, f"o marcador da mutação {nome!r} não existe mais em {arquivo}"
    # sem bytecode: duas gravações no mesmo segundo e de mesmo tamanho reaproveitariam o .pyc
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        alvo.write_text(original.replace(de, para, 1), encoding="utf-8")
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", f"{TESTES}::{teste}", "-q",
                            "-p", "no:cacheprovider"],
                           cwd=RAIZ, capture_output=True, text=True, env=ambiente)
        assert r.returncode == 1, f"a mutação {nome!r} SOBREVIVEU\n{r.stdout}"
    finally:
        alvo.write_text(original, encoding="utf-8")
