# tests/test_restricoes.py
"""As restrições do spec — o teste é a regra, não a documentação."""
import ast
import json
from pathlib import Path

import collect
from lib.coletores import http as coletor_http

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
# o runner roda comando de coleta; o build chama o Chromium para o PDF; o ignorado pergunta ao
# git se a pasta dos alvos está fora do versionamento — e mais ninguém
PODEM_EXECUTAR = {"lib/runner.py", "build_report.py", "lib/ignorado.py"}
PODEM_ABRIR_REDE = {"lib/http_get.py"}
# urllib.parse é análise de texto, não rede: quem abre socket é o de baixo
MODULOS_DE_REDE = {"socket", "ssl", "http.client", "urllib.request", "urllib.error", "requests",
                   "httpx", "ftplib", "smtplib"}


def retrato(raiz):
    return {str(p.relative_to(raiz)): (p.read_bytes() if p.is_file() else b"dir")
            for p in sorted(raiz.rglob("*"))}


def ambiente(tmp_path):
    (tmp_path / "default.toml").write_text(
        '[relatorio]\npasta = "docs/infra"\n[limites]\ntimeout_por_comando = 5\n'
        'orcamento_por_alvo = 10\nhttp_timeout = 1\n[historico]\ncomparar_com_anterior = true\n',
        encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/x"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["site"]\n', encoding="utf-8")
    return ["--padrao", str(tmp_path / "default.toml"), "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
            "--out", str(tmp_path / "docs/infra/2026-09-19_1000"), "--at", "2026-09-19T10:00:00Z"]


def test_auditar_so_escreve_na_pasta_da_execucao(tmp_path, monkeypatch):
    """Restrição 1."""
    args = ambiente(tmp_path)
    (tmp_path / "docs" / "infra").mkdir(parents=True)     # o projeto já tem auditorias anteriores
    monkeypatch.chdir(tmp_path)
    antes = retrato(tmp_path)

    collect.main([*args, "--confirmar", "site"],
                 coletores={"http": coletor_http.coletar})

    mexidos = {c for c in set(antes) | set(retrato(tmp_path)) if antes.get(c) != retrato(tmp_path).get(c)}
    fora = {c for c in mexidos if not c.startswith("docs/infra/2026-09-19_1000")}
    assert fora == set(), f"escreveu fora da pasta da execução: {sorted(fora)}"


def test_alvo_nao_confirmado_nao_gera_conexao(tmp_path, monkeypatch):
    """Restrição 3: o alvo que ficou fora do --confirmar não pode gerar UMA conexão sequer.

    Confirmar a lista vazia não prova isso: ela é barrada antes do laço. Aqui um alvo é
    confirmado e outro não, e qualquer tentativa de alcançar o segundo falha o teste.
    """
    tentativas = []
    monkeypatch.setattr(coletor_http.http_get, "get_com_status",
                        lambda url, *a, **k: tentativas.append(url) or (200, ""))
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "confirmado"\ntipo = "http"\nurl = "http://127.0.0.1:1/ok"\n\n'
        '[[alvo]]\nnome = "de_fora"\ntipo = "http"\nurl = "http://127.0.0.1:2/nao"\n',
        encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["confirmado", "de_fora"]\n',
                                                   encoding="utf-8")
    (tmp_path / "default.toml").write_text(
        '[relatorio]\npasta = "docs/infra"\n[limites]\ntimeout_por_comando = 5\n'
        'orcamento_por_alvo = 10\nhttp_timeout = 1\n[historico]\ncomparar_com_anterior = true\n',
        encoding="utf-8")
    args = ["--padrao", str(tmp_path / "default.toml"), "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
            "--out", str(tmp_path / "docs/infra/2026-09-19_1000"), "--at", "2026-09-19T10:00:00Z"]

    codigo = collect.main([*args, "--confirmar", "confirmado"],
                          coletores={"http": coletor_http.coletar})

    assert codigo == 0
    assert tentativas == ["http://127.0.0.1:1/ok"], f"alcançou alvo não confirmado: {tentativas}"


def test_confirmar_vazio_para_antes_de_qualquer_coleta(tmp_path, monkeypatch):
    tentativas = []
    monkeypatch.setattr(coletor_http.http_get, "get_com_status",
                        lambda url, *a, **k: tentativas.append(url) or (200, ""))

    codigo = collect.main([*ambiente(tmp_path), "--confirmar"],
                          coletores={"http": coletor_http.coletar})

    assert codigo == 2 and tentativas == []


def test_so_o_runner_cria_subprocesso():
    """Restrição 2 depende disto: com um ponto só, o espião de argv cobre tudo."""
    culpados = []
    for arquivo in SCRIPTS.rglob("*.py"):
        relativo = str(arquivo.relative_to(SCRIPTS))
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes = []
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom):
                nomes = [no.module or ""]
            if any(str(n).split(".")[0] in {"subprocess", "multiprocessing", "pty"} for n in nomes) \
                    and relativo not in PODEM_EXECUTAR:
                culpados.append(relativo)
    assert culpados == [], f"subprocesso fora do runner: {sorted(set(culpados))}"


def test_rede_so_nos_modulos_de_rede():
    culpados = []
    for arquivo in SCRIPTS.rglob("*.py"):
        relativo = str(arquivo.relative_to(SCRIPTS))
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes = []
            if isinstance(no, ast.Import):
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom):
                nomes = [no.module or ""]
            if any(str(n) in MODULOS_DE_REDE or str(n).split(".")[0] in {"socket", "ssl"}
                   for n in nomes) and relativo not in PODEM_ABRIR_REDE:
                culpados.append(f"{relativo}: {nomes}")
    assert culpados == [], f"rede fora dos módulos de rede: {sorted(set(culpados))}"


def test_nenhum_segredo_chega_ao_relatorio(tmp_path, monkeypatch):
    """Restrição 2: a senha não aparece no report.json, no HTML, nem no argv de nenhum comando."""
    import build_report
    from lib import runner

    argv_vistos = []
    monkeypatch.setattr(runner, "run",
                        lambda cmd, timeout, errors=None, tipo="docker":
                        argv_vistos.append(list(cmd)) or "")
    monkeypatch.setenv("SENHA_DO_ALVO", "trocadilho-secreto")
    monkeypatch.setattr(coletor_http.http_get, "get_com_status", lambda *a, **k: (200, ""))
    args = ambiente(tmp_path)
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/x"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["site"]\n', encoding="utf-8")

    collect.main([*args, "--confirmar", "site"], coletores={"http": coletor_http.coletar})
    pasta = tmp_path / "docs/infra/2026-09-19_1000"
    monkeypatch.setattr(build_report, "find_chromium", lambda: None)
    build_report.main(["--dir", str(pasta)])

    corpo = (pasta / "report.json").read_text(encoding="utf-8") + \
        (pasta / "relatorio.html").read_text(encoding="utf-8")
    assert "trocadilho-secreto" not in corpo
    assert all("trocadilho-secreto" not in " ".join(cmd) for cmd in argv_vistos)


def test_mesmo_relatorio_com_as_mesmas_entradas(tmp_path, monkeypatch):
    """Restrição 4: byte a byte, sem normalizar nada na comparação."""
    monkeypatch.chdir(tmp_path)
    saida = []
    for rodada in ("a", "b"):
        (tmp_path / rodada).mkdir()
        args = ambiente(tmp_path / rodada)
        collect.main([*args, "--confirmar", "site"], coletores={"http": coletor_http.coletar})
        saida.append((tmp_path / rodada / "docs/infra/2026-09-19_1000" / "report.json").read_bytes())

    assert saida[0] == saida[1]
