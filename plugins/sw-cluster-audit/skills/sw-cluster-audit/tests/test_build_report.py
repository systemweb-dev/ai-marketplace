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


def test_sem_details_no_pdf_e_cores_impressas():
    """No papel não dá pra clicar: nada de <details>; e o Chrome precisa de print-color-adjust."""
    out = build_report.render_html(_report())
    assert "<details" not in out
    assert "print-color-adjust:exact" in out.replace(" ", "")
    assert "@page" in out


def test_cards_de_no_com_detalhes():
    r = _report()
    r["nodes"] = [{"hostname": "mgr-1", "role": "Leader", "availability": "Active", "state": "Ready",
                   "leader": True, "reachability": "reachable", "engine": "25.0",
                   "platform": "linux/x86_64", "tasks_running": 12, "tasks_failed": 1,
                   "failed_examples": ["api.1: OOMKilled"],
                   "capacity": {"nano_cpus": 4000000000, "mem_bytes": 8000000000}}]
    out = build_report.render_html(r)
    assert "mgr-1" in out and "líder" in out
    assert "linux/x86_64" in out and "25.0" in out          # engine e plataforma
    assert "OOMKilled" in out                                # falha recente visível
    assert "4 vCPU" in out and "7.5 GB" in out               # capacidade formatada


def test_disco_e_historico_resolvidos():
    r = _report()
    r["disk"] = [{"tipo": "Images", "total": 40, "ativo": 30, "tamanho": "12GB", "recuperavel": "4GB"}]
    r["history"] = {"vs": "2026-08-17_1000", "resolved": 2, "new": 1,
                    "resolved_items": ["SEC_USER_ROOT · api"], "new_keys": [["SEC_PORT_EXPOSED", "web"]]}
    out = build_report.render_html(r)
    assert "12GB" in out and "Recuperável" in out
    assert "SEC_USER_ROOT · api" in out                      # o que foi resolvido aparece
    assert "novo" in out                                     # e o novo é marcado


def test_colapso_de_grade_e_so_na_tela():
    """No A4 a largura dispara o breakpoint mobile — o colapso precisa ser só de tela."""
    out = build_report.render_html(_report())
    assert "@media screen and (max-width:780px)" in out


def test_secao_pontos_de_impacto_com_cenario_e_consequencia():
    r = _report()
    r["impact_points"] = [{"cenario": "Se o nó mgr-1 cair",
                           "consequencia": "o ingress cai e 18 aplicações ficam inacessíveis.",
                           "impacto": "alto", "esforco": "alto",
                           "alvos": ["traefik_traefik"], "fix": "promover outro manager"}]
    out = build_report.render_html(r)
    assert "Pontos de impacto" in out
    assert "Se o nó mgr-1 cair" in out and "18 aplicações ficam inacessíveis" in out
    assert "promover outro manager" in out and "impacto alto" in out


def test_saude_verde_mostra_saudavel():
    r = _report()
    r["health"]["verdict"] = "green"
    r["dimensions"]["operacao"] = {"note": "green", "services_up": 56, "services_total": 56,
                                   "stopped": 0, "failing": 0, "nodes_down": 0}
    out = build_report.render_html(r)
    assert "Saudável" in out and "56/56 serviços no ar" in out
