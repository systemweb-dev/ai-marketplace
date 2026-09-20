# tests/test_build_pdf_motivo.py
"""Quando o PDF não sai, o motivo tem que ser o verdadeiro.

A mensagem antiga era "PDF não gerado (sem Chromium)" para QUALQUER falha. Numa máquina com
Chromium instalado e uma conversão que estourou o tempo, ela mandava o operador procurar um
navegador que já estava lá.
"""
import subprocess

import pytest

import build_report


@pytest.fixture
def relatorio_minimo():
    return {"schema_version": 3, "generated_at": "2026-09-19T22:00:00Z",
            "alvos": [], "resumo": "", "recomendacoes": [],
            "fortes": [], "fracos": [], "aceites": [], "inventario": []}


def test_sem_chromium_diz_que_falta_chromium(tmp_path, relatorio_minimo, monkeypatch):
    monkeypatch.setattr(build_report, "find_chromium", lambda: None)

    res = build_report.build(relatorio_minimo, tmp_path, formato="html+pdf")

    assert res["pdf"] is None
    assert "Chromium" in res["pdf_motivo"]


def test_falha_da_conversao_nao_e_confundida_com_falta_de_navegador(
        tmp_path, relatorio_minimo, monkeypatch):
    monkeypatch.setattr(build_report, "find_chromium", lambda: "/usr/bin/google-chrome")

    def estoura(*a, **k):
        raise subprocess.TimeoutExpired(cmd="chrome", timeout=60)

    monkeypatch.setattr(build_report.subprocess, "run", estoura)

    res = build_report.build(relatorio_minimo, tmp_path, formato="html+pdf")

    assert res["pdf"] is None
    motivo = res["pdf_motivo"].lower()
    assert "não encontrado" not in motivo and "instale" not in motivo, \
        "mandou instalar o navegador que já está instalado"
    assert str(build_report.PDF_TIMEOUT) in res["pdf_motivo"]
    assert "tempo" in res["pdf_motivo"].lower()


def test_html_sai_mesmo_quando_o_pdf_falha(tmp_path, relatorio_minimo, monkeypatch):
    """O HTML é o produto; o PDF é o extra. Um não pode levar o outro."""
    monkeypatch.setattr(build_report, "find_chromium", lambda: "/usr/bin/google-chrome")
    monkeypatch.setattr(build_report.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disco cheio")))

    res = build_report.build(relatorio_minimo, tmp_path, formato="html+pdf")

    assert res["html"] and (tmp_path / "relatorio.html").exists()
    assert "disco cheio" in res["pdf_motivo"]


def test_formato_html_nao_inventa_motivo(tmp_path, relatorio_minimo):
    """Ninguém pediu PDF: não há falha a relatar."""
    res = build_report.build(relatorio_minimo, tmp_path, formato="html")

    assert res["pdf"] is None and res["pdf_motivo"] is None
