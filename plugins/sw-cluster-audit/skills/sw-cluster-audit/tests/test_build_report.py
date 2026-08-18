import json
import pathlib

import build_report

FX = pathlib.Path(__file__).parent / "fixtures"


def _report():
    return json.loads((FX / "report_sample.json").read_text())


def test_render_html_self_contained_e_sem_vazar_valor():
    out = build_report.render_html(_report())
    assert "http://" not in out.replace("http://10.0.0.1:9090", "")  # só o endpoint citado como texto
    assert "https://" not in out                                     # zero asset remoto
    assert "DB_PASSWORD" not in out or "supersecret" not in out      # nunca valor de env


def test_render_html_escapa_dado_do_cluster():
    r = _report()
    r["services"][0]["name"] = "<script>alert(1)</script>"
    out = build_report.render_html(r)
    assert "<script>alert(1)</script>" not in out and "&lt;script&gt;" in out


def test_narrativa_e_recomendacao_com_comando():
    out = build_report.render_html(_report())
    assert "ponto único" in out                                   # summary
    assert "Todos os nodes Ready" in out                           # fortes
    assert "banco sem HA" in out                                   # fracos
    assert "Subir 2ª réplica do Traefik" in out                    # recomendação
    assert "docker service update --replicas 2 traefik_traefik" in out   # O QUE FAZER (comando)


def test_dimensoes_kpis_e_historico():
    out = build_report.render_html(_report())
    assert "Segurança" in out and "Disponibilidade" in out and "Higiene" in out
    assert "aplicações" in out and "requests 24h" in out           # KPIs
    assert "auditoria anterior" in out and "resolvidos" in out     # diff histórico


def test_agrupamento_por_stack_e_runtime():
    out = build_report.render_html(_report())
    assert "Por aplicação" in out
    assert "challenge-api" in out and "traefik" in out             # stacks como blocos
    assert "128,4 mil req/24h" in out                              # métrica de runtime do Traefik
    assert "12.4% CPU" in out                                      # métrica de runtime do app


def test_findings_agrupados_e_explicados():
    out = build_report.render_html(_report())
    assert "Container privilegiado" in out and "Por que importa:" in out
    assert "Como corrigir:" in out


def test_degrada_sem_chromium(monkeypatch, tmp_path):
    monkeypatch.setattr(build_report, "find_chromium", lambda: None)
    res = build_report.build(_report(), tmp_path)
    assert (tmp_path / "relatorio.html").exists() and res["pdf"] is None


def test_secao_na_mostra_aviso():
    r = _report()
    r["nodes"] = {"status": "n/a", "reason": "timeout"}
    out = build_report.render_html(r)
    assert "não coletado" in out and "timeout" in out


def test_summary_permite_negrito_mas_bloqueia_html_perigoso():
    r = _report()
    r["summary"] = "Risco <strong>alto</strong> <script>alert(1)</script>"
    out = build_report.render_html(r)
    assert "<strong>alto</strong>" in out                    # negrito passa
    assert "<script>alert(1)</script>" not in out            # script não


def test_comando_multilinha_quebra_de_verdade():
    r = _report()
    r["recommendations"][0]["command"] = "# passo 1\\ndocker service update --replicas 2 x"
    out = build_report.render_html(r)
    assert "\\n" not in out.split('class="cmd"')[1][:300]      # nada de \n literal
    assert "docker service update --replicas 2 x" in out
