import json
import pathlib

import build_report

FX = pathlib.Path(__file__).parent / "fixtures"


def _report():
    return json.loads((FX / "report_sample.json").read_text())


def test_render_html_tem_semaforo_findings_e_self_contained():
    out = build_report.render_html(_report())
    assert "🔴" in out and "Crítico" in out                 # semáforo (verdict=red)
    assert "SEC_PRIVILEGED" in out and "SEC_PORT_EXPOSED" in out  # findings agrupados (rule_id)
    assert "http://" not in out and "https://" not in out    # self-contained (zero asset remoto)


def test_render_html_secoes_novas():
    out = build_report.render_html(_report())
    # narrativa do agente
    assert "ponto único" in out                                    # summary
    assert "Todos os nodes Ready" in out                           # pontos fortes
    assert "3 bancos sem HA" in out                                # pontos fracos
    assert "Subir 2ª réplica do Traefik" in out                    # recomendação
    # métricas por dimensão + explicação dos findings + histórico
    assert "Segurança" in out and "Disponibilidade" in out and "Higiene" in out
    assert "Container privilegiado" in out and "Por que importa:" in out  # finding agrupado + explicado
    assert "vs auditoria anterior" in out and "resolvidos" in out   # diff histórico


def test_render_html_escapa_e_nao_vaza_valor():
    r = _report()
    r["services"][0]["name"] = "<script>alert(1)</script>"   # dado do cluster não injeta HTML
    out = build_report.render_html(r)
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_degrada_sem_chromium(monkeypatch, tmp_path):
    monkeypatch.setattr(build_report, "find_chromium", lambda: None)
    res = build_report.build(_report(), tmp_path)
    assert (tmp_path / "relatorio.html").exists() and res["pdf"] is None   # HTML sai, PDF n/a


def test_secao_componentes_com_kind_roteamento_e_analise():
    r = _report()
    r["services"][0]["kind"] = "ingress/proxy"
    r["services"][0]["routing_labels"] = {"traefik.http.routers.web.rule": "Host(`app.x`)"}
    r["components_analysis"] = {"web": "Traefik roteia app.x; 1 réplica (gargalo potencial)"}
    out = build_report.render_html(r)
    assert "Análise por componente" in out
    assert "ingress/proxy" in out and "Host(`app.x`)" in out    # tipo + regra de roteamento
    assert "gargalo potencial" in out                           # análise do agente renderizada


def test_secao_na_mostra_aviso():
    r = _report()
    r["nodes"] = {"status": "n/a", "reason": "timeout"}
    out = build_report.render_html(r)
    assert "não coletado" in out and "timeout" in out
