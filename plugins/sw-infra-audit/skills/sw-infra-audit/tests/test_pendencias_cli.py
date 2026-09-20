# tests/test_pendencias_cli.py
"""A SKILL.md manda rodar este script no passo 3b. Ponteiro para script que não roda é pior
que ponteiro nenhum: o agente tenta, falha, e segue sem a checagem."""
import json

import pendencias


def _escrever(tmp_path, relatorio):
    (tmp_path / "report.json").write_text(json.dumps(relatorio), encoding="utf-8")
    return tmp_path


def test_lista_o_que_esta_calado_e_o_motivo(tmp_path, capsys):
    d = _escrever(tmp_path, {"alvos": [{"nome": "prod", "componentes": [
        {"nome": "traefik", "papel": "entrada", "respostas": [
            {"pergunta": "entrada.latencia", "sem_dados": True,
             "motivo": "o componente não declara `metricas_url` no alvos.toml"}]}]}]})

    assert pendencias.main(["--dir", str(d)]) == 0
    saida = capsys.readouterr().out
    assert "traefik" in saida and "metricas_url" in saida


def test_sem_pendencia_diz_que_esta_completo(tmp_path, capsys):
    d = _escrever(tmp_path, {"alvos": [{"nome": "prod", "componentes": [
        {"nome": "traefik", "papel": "entrada",
         "respostas": [{"pergunta": "entrada.latencia", "valor": 3, "fonte": "promql"}]}]}]})

    assert pendencias.main(["--dir", str(d)]) == 0
    assert "nenhuma pendência" in capsys.readouterr().out


def test_pasta_sem_report_sai_com_erro_e_nao_explode(tmp_path, capsys):
    assert pendencias.main(["--dir", str(tmp_path)]) == 2
    assert "não consegui ler" in capsys.readouterr().err
