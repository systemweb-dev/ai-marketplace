"""O papel chega ao relatório com a origem — pelo mesmo motivo que toda medida chega com a
fonte que respondeu. E quando a evidência CONTRADIZ a imagem, o relatório diz que corrigiu:
é a imagem mentindo, à vista, e isso é informação acionável."""
import build_report


def _componente(**kw):
    base = {"nome": "infra_broker", "papel": "fila", "papel_origem": "declarado",
            "respostas": []}
    return dict(base, **kw)


def test_papel_confirmado_mostra_a_fonte():
    html = build_report._origem_do_papel(
        _componente(papel_origem="exporter rabbitmq-prometheus"))

    assert "confirmado pelo exporter" in html


def test_papel_sugerido_pela_imagem_diz_que_e_palpite():
    html = build_report._origem_do_papel(_componente(papel_origem="imagem"))

    assert "sugerido pela imagem, não confirmado" in html
    # a asserção ingênua `"confirmado" not in html` passava por acidente ao contrário: ela
    # casava dentro de "não confirmado"
    assert "confirmado pelo exporter" not in html


def test_papel_declarado_diz_que_foi_o_dono():
    html = build_report._origem_do_papel(_componente(papel_origem="declarado"))

    assert "declarado no alvos.toml" in html


def test_contradicao_entre_imagem_e_evidencia_aparece():
    html = build_report._origem_do_papel(
        _componente(papel="fila", papel_origem="exporter rabbitmq-prometheus",
                    papel_da_imagem="banco"))

    assert "a imagem sugeria banco" in html


def test_sem_evidencia_nenhuma_o_relatorio_nao_finge():
    html = build_report._origem_do_papel(_componente(papel_origem="padrão"))

    assert "nenhuma fonte reconheceu" in html


def test_a_limitacao_do_kind_e_declarada_no_relatorio():
    """D5: saúde e impacto continuam classificando pela imagem. Deixar isso implícito faria o
    relatório dizer duas coisas sobre o mesmo componente sem explicar por quê."""
    assert "classificam pela imagem" in build_report.NOTA_DO_PAPEL


def test_a_nota_e_a_origem_chegam_ao_HTML():
    """Sem este teste, `_papel_com_origem` e `NOTA_DO_PAPEL` existiriam, seriam testados, e
    nunca apareceriam no relatório — D3 e D5 não chegariam a quem lê."""
    alvo = {"nome": "c", "tipo": "docker", "onde": "ctx", "saude": "🟢", "achados": [],
            "componentes": [_componente(papel_origem="exporter rabbitmq-prometheus",
                                        papel_da_imagem="banco",
                                        analise="o broker mede.")]}

    html = build_report._camada_bloco("Enfileira", "fila", "",
                                      alvo["componentes"])

    assert "confirmado pelo exporter" in html
    assert "a imagem sugeria banco" in html


def test_a_nota_da_limitacao_chega_ao_HTML():
    """D5 diz que a limitação é DECLARADA no relatório. Ela já existiu numa função órfã que
    `build()` nunca chamou — existir e ser testada não é chegar a quem lê."""
    # `_topologia` tem a MESMA legenda e é órfã — `build()` não a chama. Asserir contra ela
    # seria o mesmo verde falso que fez esta nota não chegar ao PDF duas vezes.
    html = build_report._camadas([{"nome": "x", "papel": "app", "papel_origem": "padrão",
                                   "respostas": []}])

    assert "classificam pela imagem" in html


def test_cada_camada_do_relatorio_tem_titulo_proprio():
    """Quatro papéis compartilhavam o rótulo "guarda", e saíam como seções numeradas repetidas
    (`04 Guarda`, `05 Guarda`). Era invisível enquanto um fork de cache caía em `app`: só
    apareceu quando o papel passou a ser provado pela série."""
    rotulos = [rotulo for _, rotulo in build_report.CAMADAS]

    assert len(rotulos) == len(set(rotulos)), rotulos


def test_o_motivo_de_duas_familias_nao_le_como_um_nome_so():
    """Visto num relatório real: "o exporter cadvisor, traefik não expõe o dado desta
    pergunta" — correto no conteúdo, e lê como se `cadvisor, traefik` fosse um produto."""
    import collect
    from lib.adaptadores import promql

    familias = [{"familia": {"familia": n, "pergunta": []}, "seletor": ""}
                for n in ("cadvisor", "traefik")]
    contexto = {"timeout": 2, "cache": {"resolvido": {"x": {"familias": familias}}}}

    r = promql.perguntar("banco.conexoes", {"nome": "x", "metricas_url": "http://f"}, contexto)

    assert r["motivo"] == "os exporters cadvisor e traefik não expõem o dado desta pergunta"
