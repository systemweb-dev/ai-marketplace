# tests/test_regras_de_fila.py
"""A regra que nasce de medida, não de inspeção de configuração.

Todas as regras anteriores da skill olhavam para como o serviço está DECLARADO (roda como root,
imagem sem digest, sem healthcheck). Esta olha para o que está ACONTECENDO — e por isso depende
de uma coleta que respondeu, nunca de uma que falhou.
"""
from lib.regras import REGRAS, esperada, exigem_remediacao, severidade
from lib.remediacao import para


def test_a_regra_esta_no_registro():
    assert "fila_sem_consumidor" in REGRAS


def test_severidade_padrao_bate_com_o_limiar_da_pergunta():
    """Dois lugares declaram severidade: o limiar da pergunta e o registro. Divergir faria o
    relatório mostrar uma e a nota do alvo usar a outra."""
    from lib.perguntas import PERGUNTAS

    limiar = PERGUNTAS["fila.filas"]["limiar"]

    assert severidade(limiar["regra"]) == limiar["severidade"]


def test_nao_e_esperada():
    """`esperada` marca comportamento NORMAL. Fila sem consumidor com mensagem presa não é."""
    assert not esperada("fila_sem_consumidor")


def test_exige_remediacao():
    assert "fila_sem_consumidor" in exigem_remediacao()


def test_a_remediacao_tem_os_quatro_blocos():
    bloco = para("fila_sem_consumidor")

    assert bloco is not None, "fila_sem_consumidor sem arquivo de remediação"
    for campo in ("por_que_importa", "como_resolver", "como_confirmar", "quando_nao_fazer"):
        assert bloco.get(campo), f"bloco {campo} vazio"


def test_a_origem_diz_de_onde_a_regra_nasce():
    """`origem` é o que permite responder "quem emite isto?" sem ler AST."""
    assert REGRAS["fila_sem_consumidor"]["origem"] == "limiar"


def test_a_remediacao_traz_um_comando_para_rodar():
    """Remover o bloco de comando inteiro passava com a suíte verde."""
    assert "```" in para("fila_sem_consumidor")["como_resolver"]


def test_nenhum_comando_de_remediacao_poe_senha_no_argv():
    """`curl -u "$USUARIO:$SENHA"` expande a senha no argv: fica visível em `ps`, em
    `/proc/*/cmdline` e na transcrição do agente. A remediação ensinava justamente o que
    `lib/credencial.py` existe para evitar. Vale para todos os arquivos, não só este."""
    import re

    from lib.remediacao import disponiveis

    for regra in sorted(disponiveis()):
        texto = para(regra)["como_resolver"]
        assert not re.search(r"-u\s+\S*:\$", texto), f"{regra}: senha no argv"
        assert not re.search(r"(?i)(senha|password|pass)=\$", texto), f"{regra}: senha no argv"


def test_remediacao_nao_traz_endereco_literal():
    """Comando exibido usa variável (`$ADMIN_URL`), nunca endereço escrito: o repositório é
    público e o texto vai para o relatório. A versão anterior deste teste barrava só `.com.br`,
    e `https://rabbitmq.empresa.com:15672` passava."""
    import re

    texto = " ".join(str(v) for v in para("fila_sem_consumidor").values())

    assert not re.search(r"https?://[A-Za-z0-9]", texto)
    assert not re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", texto)


def test_quando_nao_fazer_documenta_os_falsos_positivos_conhecidos():
    """A regra acusa fila morta, fila de retry e stream, que ficam sem consumidor por desenho.
    Com a pergunta de fila morta fora da v1, calar isso faria o relatório rotular fila morta
    como "fila sem consumidor, alto" sem explicar."""
    texto = para("fila_sem_consumidor")["quando_nao_fazer"].lower()

    for caso in ("fila morta", "stream", "nova tentativa"):
        assert caso in texto, f"falso positivo não documentado: {caso}"
